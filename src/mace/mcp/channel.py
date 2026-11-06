"""
MACE - Mobile AArch64 Context Extension
mcp/channel.py

The lldb-side half of MACE's AI-pipeline integration (v3). Hosts a
Unix domain socket inside the live lldb session; the separate MACE
MCP server process (not implemented yet -- step 2) connects to this
socket and relays MCP tool calls through it. This module deliberately
knows nothing about MCP itself -- it is a small JSON request/response
loop plus a tool registry, so it can be tested and used independently
of whether an MCP server is on the other end at all.

Protocol: newline-delimited JSON over the socket. One line in, one
line out, per request. No framing beyond the newline -- callers must
not embed a literal newline inside a request/response payload (JSON
encoding handles this automatically).

Request:  {"tool": "<name>", "args": {...}}
Response: {"ok": true, "result": <any>} or {"ok": false, "error": "<msg>"}

Tool registry: name -> {"fn": callable(debugger, args) -> JSON-
serializable result, "tier": "session"|"diagnostics"|"analyst",
"mode": "read"|"write"}. tier/mode are metadata only for now
(extension seam #4, ROADMAP 2026-11-03) -- nothing routes on them
yet; mode will drive the auto-approve-vs-ask permission gate once the
orchestrator (step 3) exists. Ships with "ping" (the step-1 proof),
"mace_get_register_context", "mace_read_memory",
"mace_get_backtrace", "mace_set_breakpoint", and "mace_patch"
(step 2) registered.

Thread safety (known, documented limitation -- see BACKLOG.md): the
listener runs in a background thread, separate from lldb's own
stop-hook callback thread. Every tool-registry call is serialized
through LLDB_LOCK below, which prevents two concurrent MCP calls from
racing each other. It does NOT currently prevent a race between this
channel's thread and stop_hook.py's handle_stop -- that would require
sharing a single lock across both call sites, deferred as a scoped
decision for Dec (CB, 2026-11-03).
"""

import lldb

import dataclasses
import json
import os
import socket
import threading
import time

from mace.core import findings, patch_history
from mace.lldb.lldb_session import snapshot_from_frame, _get_breakpoint_id

LLDB_LOCK = threading.Lock()

# Cap on a single mace_read_memory request, bytes. Prevents an
# accidental huge read from hanging the channel thread or blowing up
# the JSON response size.
MAX_READ_SIZE = 4096

# Cap on a single mace_get_backtrace request, frames. Same rationale
# as MAX_READ_SIZE -- bounds response size and lldb API work per call.
MAX_BACKTRACE_FRAMES = 64

# Cap on a single mace_continue request's wait, seconds. mace_continue
# blocks the channel's listener thread until the process reaches a
# terminal state (stopped/crashed/exited/detached) or this timeout
# elapses -- unlike every other tool, a continue can legitimately run
# for a long time (or never return, if a breakpoint never fires), so
# this bounds the worst case rather than leaving the thread wedged.
MAX_CONTINUE_TIMEOUT = 120

# name -> {"fn": callable(debugger, args) -> JSON-serializable result,
#          "tier": "session" | "diagnostics" | "analyst",
#          "mode": "read" | "write"}
# tier/mode are metadata only for now (extension seam #4, ROADMAP
# 2026-11-03) -- nothing routes on them yet. mode will drive the
# auto-approve-vs-ask permission gate once the orchestrator (step 3)
# exists.
_TOOLS = {}

_listener_thread = None
_server_socket = None
_shutdown = threading.Event()



def register_tool(name, fn, tier="diagnostics", mode="read"):
    """Register a tool handler. fn(debugger, args) -> JSON-serializable result."""
    _TOOLS[name] = {"fn": fn, "tier": tier, "mode": mode}


def _add_hex_fields(snapshot):
    """Add pc_hex/lr_hex/sp_hex/fp_hex companion fields to a
    ContextSnapshot's asdict() output. The decimal fields are accurate
    (confirmed byte-for-byte against lldb's own output repeatedly) but
    awkward for an LLM consumer to hex-convert by hand -- confirmed
    live (2026-11-04, 2026-11-05) to produce garbled/wrong hex in the
    agent's own narration while the underlying decimal data stayed
    correct. Purely additive -- every existing field is untouched."""
    for field in ("pc", "lr", "sp", "fp"):
        value = snapshot.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            snapshot[f"{field}_hex"] = f"0x{value:x}"
    return snapshot


def _handle_ping(debugger, args):
    return {"pong": True}


register_tool("ping", _handle_ping, tier="session", mode="read")


def _handle_get_register_context(debugger, args):
    target = debugger.GetSelectedTarget()
    if not target or not target.IsValid():
        raise RuntimeError("no valid target")
    process = target.GetProcess()
    if not process or not process.IsValid():
        raise RuntimeError("no running process")
    thread = process.GetSelectedThread()
    if not thread or not thread.IsValid():
        raise RuntimeError("no selected thread")
    frame = thread.GetSelectedFrame()
    if not frame or not frame.IsValid():
        raise RuntimeError("no selected frame")
    snap = snapshot_from_frame(frame)
    return _add_hex_fields(dataclasses.asdict(snap))


register_tool("mace_get_register_context", _handle_get_register_context,
              tier="diagnostics", mode="read")


def _handle_read_memory(debugger, args):
    target = debugger.GetSelectedTarget()
    if not target or not target.IsValid():
        raise RuntimeError("no valid target")
    process = target.GetProcess()
    if not process or not process.IsValid():
        raise RuntimeError("no running process")

    address = args.get("address")
    size = args.get("size")
    if address is None:
        raise ValueError("'address' is required")
    if size is None:
        raise ValueError("'size' is required")
    if isinstance(address, str):
        address = int(address, 0)  # accepts "0x..." or a plain decimal string
    if not isinstance(address, int) or isinstance(address, bool):
        raise ValueError("'address' must be an int or a numeric string")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("'size' must be a positive integer")
    if size > MAX_READ_SIZE:
        raise ValueError(f"'size' exceeds max of {MAX_READ_SIZE} bytes")

    error = lldb.SBError()
    data = process.ReadMemory(address, size, error)
    if not error.Success():
        raise RuntimeError(f"ReadMemory failed: {error.GetCString()}")

    return {"address": f"0x{address:x}", "size": size, "hex": data.hex()}


register_tool("mace_read_memory", _handle_read_memory,
              tier="diagnostics", mode="read")


def _handle_get_backtrace(debugger, args):
    target = debugger.GetSelectedTarget()
    if not target or not target.IsValid():
        raise RuntimeError("no valid target")
    process = target.GetProcess()
    if not process or not process.IsValid():
        raise RuntimeError("no running process")
    thread = process.GetSelectedThread()
    if not thread or not thread.IsValid():
        raise RuntimeError("no selected thread")

    max_frames = args.get("max_frames", 32)
    if not isinstance(max_frames, int) or isinstance(max_frames, bool) or max_frames <= 0:
        raise ValueError("'max_frames' must be a positive integer")
    max_frames = min(max_frames, MAX_BACKTRACE_FRAMES)

    num_frames = thread.GetNumFrames()
    frames = []
    for i in range(min(num_frames, max_frames)):
        frame = thread.GetFrameAtIndex(i)
        function = frame.GetFunction()
        symbol = frame.GetSymbol()
        if function.IsValid():
            name = function.GetName()
        elif symbol.IsValid():
            name = symbol.GetName()
        else:
            name = "<unknown>"
        module = frame.GetModule()
        module_name = module.GetFileSpec().GetFilename() if module.IsValid() else ""
        line_entry = frame.GetLineEntry()
        file_line = ""
        if line_entry.IsValid() and line_entry.GetFileSpec().IsValid():
            file_line = f"{line_entry.GetFileSpec().GetFilename()}:{line_entry.GetLine()}"
        frames.append({
            "index": i,
            "pc": f"0x{frame.GetPC():x}",
            "function": name,
            "module": module_name,
            "file_line": file_line,
        })

    return {"frame_count": num_frames, "frames": frames}


register_tool("mace_get_backtrace", _handle_get_backtrace,
              tier="diagnostics", mode="read")


def _handle_set_breakpoint(debugger, args):
    target = debugger.GetSelectedTarget()
    if not target or not target.IsValid():
        raise RuntimeError("no valid target")

    symbol = args.get("symbol")
    address = args.get("address")
    offset = args.get("offset", 0)
    module_name = args.get("module")

    if not symbol and address is None:
        raise ValueError("'symbol' or 'address' is required")
    if not isinstance(offset, int) or isinstance(offset, bool):
        raise ValueError("'offset' must be an integer")
    if offset and not symbol:
        raise ValueError("'offset' requires 'symbol'")
    if offset and not module_name:
        raise ValueError(
            "'offset' requires 'module' (the binary's loaded name, e.g. "
            "'libfoo.so') to resolve the symbol against the right image"
        )

    bp = None
    if symbol and offset:
        module = target.FindModule(lldb.SBFileSpec(module_name))
        if not module.IsValid():
            raise RuntimeError(f"module '{module_name}' not found in target")
        symbol_obj = module.FindSymbol(symbol, lldb.eSymbolTypeCode)
        if not symbol_obj.IsValid():
            raise RuntimeError(f"symbol '{symbol}' not found in module '{module_name}'")
        file_addr = symbol_obj.GetStartAddress().GetFileAddress()
        sb_addr = module.ResolveFileAddress(file_addr + offset)
        if not sb_addr.IsValid():
            raise RuntimeError(f"could not resolve {symbol}+{offset} in '{module_name}'")
        bp = target.BreakpointCreateBySBAddress(sb_addr)
    elif symbol:
        bp = target.BreakpointCreateByName(symbol)
    else:
        if isinstance(address, str):
            address = int(address, 0)
        if not isinstance(address, int) or isinstance(address, bool):
            raise ValueError("'address' must be an int or a numeric string")
        bp = target.BreakpointCreateByAddress(address)

    if bp is None or not bp.IsValid() or bp.GetNumLocations() == 0:
        raise RuntimeError("breakpoint could not be resolved to any location")

    locations = [f"0x{bp.GetLocationAtIndex(i).GetLoadAddress():x}"
                 for i in range(bp.GetNumLocations())]

    return {
        "breakpoint_id": bp.GetID(),
        "num_locations": bp.GetNumLocations(),
        "locations": locations,
    }


register_tool("mace_set_breakpoint", _handle_set_breakpoint,
              tier="analyst", mode="write")


def _handle_patch(debugger, args):
    target = debugger.GetSelectedTarget()
    if not target or not target.IsValid():
        raise RuntimeError("no valid target")
    process = target.GetProcess()
    if not process or not process.IsValid() or process.GetState() != lldb.eStateStopped:
        raise RuntimeError("cannot patch -- process is not stopped")
    thread = process.GetSelectedThread()
    if not thread or not thread.IsValid():
        raise RuntimeError("no selected thread")
    frame = thread.GetSelectedFrame()
    if not frame or not frame.IsValid():
        raise RuntimeError("no valid stack frame")

    reg_name = args.get("register")
    value = args.get("value")
    if not reg_name:
        raise ValueError("'register' is required")
    if value is None:
        raise ValueError("'value' is required")

    reg_value = frame.FindRegister(reg_name)
    if not reg_value.IsValid():
        raise ValueError(f"unknown register '{reg_name}'")

    if isinstance(value, str):
        new_value = int(value, 0)
    elif isinstance(value, int) and not isinstance(value, bool):
        new_value = value
    else:
        raise ValueError("'value' must be an int or a numeric string")

    old_value = reg_value.GetValueAsUnsigned()

    error = lldb.SBError()
    reg_value.SetValueFromCString(f"0x{new_value:x}", error)
    if not error.Success():
        raise RuntimeError(f"patch failed: {error.GetCString()}")

    # Read back to confirm the write actually took, same discipline as
    # MACEPatch (stop_hook.py) -- don't trust SetValueFromCString's
    # success flag alone.
    confirmed_value = reg_value.GetValueAsUnsigned()

    pc = frame.GetPC()
    bp_id = _get_breakpoint_id(thread)
    func_name = frame.GetFunctionName() or "?"

    record = {
        "register":      reg_name,
        "old_value":     old_value,
        "new_value":     confirmed_value,
        "pc":            pc,
        "breakpoint_id": bp_id,
        "function":      func_name,
        "timestamp":     time.strftime("%H:%M:%S"),
    }
    patch_history.record_patch(record)

    response = {
        "register": reg_name,
        "old_value": f"0x{old_value:x}",
        "new_value": f"0x{confirmed_value:x}",
        "pc": f"0x{pc:x}",
        "function": func_name,
        "breakpoint_id": bp_id,
    }
    if confirmed_value != new_value:
        response["warning"] = (
            f"requested 0x{new_value:x} but register reads back as "
            f"0x{confirmed_value:x} -- write may have been truncated "
            f"to the register's actual width"
        )
    return response


register_tool("mace_patch", _handle_patch, tier="analyst", mode="write")


def _handle_step_instruction(debugger, args):
    target = debugger.GetSelectedTarget()
    if not target or not target.IsValid():
        raise RuntimeError("no valid target")
    process = target.GetProcess()
    if not process or not process.IsValid() or process.GetState() != lldb.eStateStopped:
        raise RuntimeError("cannot step -- process is not stopped")
    thread = process.GetSelectedThread()
    if not thread or not thread.IsValid():
        raise RuntimeError("no selected thread")
    frame = thread.GetSelectedFrame()
    if not frame or not frame.IsValid():
        raise RuntimeError("no valid stack frame")

    step_over = bool(args.get("over", False))
    old_pc = frame.GetPC()
    old_function = frame.GetFunctionName() or "?"

    was_async = debugger.GetAsync()
    debugger.SetAsync(False)
    try:
        thread.StepInstruction(step_over)
    finally:
        debugger.SetAsync(was_async)

    new_thread = process.GetSelectedThread()

    if not new_thread or not new_thread.IsValid():
        raise RuntimeError("step completed but no valid thread afterward")
    new_frame = new_thread.GetSelectedFrame()
    if not new_frame or not new_frame.IsValid():
        raise RuntimeError("step completed but no valid stack frame afterward")

    snapshot = _add_hex_fields(dataclasses.asdict(snapshot_from_frame(new_frame)))
    snapshot["old_pc"] = f"0x{old_pc:x}"
    snapshot["old_function"] = old_function
    snapshot["step_over"] = step_over
    return snapshot


register_tool("mace_step_instruction", _handle_step_instruction, tier="analyst", mode="write")


def _handle_continue(debugger, args):
    target = debugger.GetSelectedTarget()
    if not target or not target.IsValid():
        raise RuntimeError("no valid target")
    process = target.GetProcess()
    if not process or not process.IsValid() or process.GetState() != lldb.eStateStopped:
        raise RuntimeError("cannot continue -- process is not stopped")

    timeout = args.get("timeout_seconds", 30)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("'timeout_seconds' must be a positive number")
    timeout = min(timeout, MAX_CONTINUE_TIMEOUT)

    listener = lldb.SBListener("mace_continue_listener")
    process.GetBroadcaster().AddListener(listener, lldb.SBProcess.eBroadcastBitStateChanged)

    was_async = debugger.GetAsync()
    debugger.SetAsync(True)
    final_state = None
    try:
        err = process.Continue()
        if not err.Success():
            raise RuntimeError(f"continue failed: {err.GetCString()}")

        deadline = time.monotonic() + timeout
        event = lldb.SBEvent()
        while time.monotonic() < deadline:
            # WaitForEvent's timeout must be a whole-second integer
            # (uint32_t) -- poll in 1s slices and let this loop's own
            # float-based deadline decide the real overall cutoff.
            if not listener.WaitForEvent(1, event):
                continue
            if not lldb.SBProcess.EventIsProcessEvent(event):
                continue
            state = lldb.SBProcess.GetStateFromEvent(event)
            if state in (lldb.eStateStopped, lldb.eStateCrashed,
                         lldb.eStateExited, lldb.eStateDetached):
                final_state = state
                break
            # eStateRunning and other transient states -- keep waiting
    finally:
        process.GetBroadcaster().RemoveListener(listener, lldb.SBProcess.eBroadcastBitStateChanged)
        debugger.SetAsync(was_async)

    if final_state is None:
        return {
            "status": "timeout",
            "timeout_seconds": timeout,
            "note": "process did not reach a stopped/crashed/exited state "
                    "within the timeout; it may still be running. Check "
                    "state with another tool, or call mace_continue again "
                    "once it settles.",
        }

    if final_state == lldb.eStateExited:
        return {"status": "exited", "exit_status": process.GetExitStatus()}
    if final_state == lldb.eStateDetached:
        return {"status": "detached"}

    thread = process.GetSelectedThread()
    if not thread or not thread.IsValid():
        return {"status": "stopped", "note": "no valid thread after continue"}
    frame = thread.GetSelectedFrame()
    if not frame or not frame.IsValid():
        return {"status": "stopped", "note": "no valid frame after continue"}

    snapshot = _add_hex_fields(dataclasses.asdict(snapshot_from_frame(frame)))
    snapshot["status"] = "crashed" if final_state == lldb.eStateCrashed else "stopped"
    return snapshot


register_tool("mace_continue", _handle_continue, tier="analyst", mode="write")


def _handle_get_findings(debugger, args):
    """Return every currently-loaded finding (from mace_load_findings),
    keyed by the lldb breakpoint ID mace_load_findings already set for
    it. Read-only -- this doesn't set or change anything, it just lets
    an MCP caller see what a human operator running mace_load_findings
    already set up, instead of guessing symbol names blind (see
    BACKLOG.md's 2026-11-05 entry)."""
    result = []
    for breakpoint_id, finding in findings.list_active_findings():
        entry = dataclasses.asdict(finding)
        entry["breakpoint_id"] = breakpoint_id
        result.append(entry)
    return {"findings": result}


register_tool("mace_get_findings", _handle_get_findings, tier="diagnostics", mode="read")


def _dispatch(debugger, request):
    tool = request.get("tool")
    args = request.get("args", {})
    if tool is None:
        return {"ok": False, "error": "request missing 'tool'"}
    entry = _TOOLS.get(tool)
    if entry is None:
        return {"ok": False, "error": f"unknown tool: {tool!r}"}
    try:
        with LLDB_LOCK:
            result = entry["fn"](debugger, args)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _serve_client(debugger, conn):
    with conn:
        buf = b""
        while not _shutdown.is_set():
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    request = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError as e:
                    response = {"ok": False, "error": f"invalid JSON: {e}"}
                else:
                    response = _dispatch(debugger, request)
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))


def _accept_loop(debugger, sock):
    while not _shutdown.is_set():
        try:
            sock.settimeout(1.0)
            conn, _ = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        _serve_client(debugger, conn)


def start(debugger, socket_path):
    """Start the listener thread on socket_path. Raises if already running."""
    global _listener_thread, _server_socket
    if _listener_thread is not None and _listener_thread.is_alive():
        raise RuntimeError("MACE MCP channel already running")
    if os.path.exists(socket_path):
        os.remove(socket_path)
    _shutdown.clear()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(socket_path)
    sock.listen(1)
    _server_socket = sock
    _listener_thread = threading.Thread(
        target=_accept_loop, args=(debugger, sock), daemon=True
    )
    _listener_thread.start()
    return socket_path


def stop():
    """Stop the listener thread, if running."""
    global _listener_thread, _server_socket
    _shutdown.set()
    if _server_socket is not None:
        try:
            _server_socket.close()
        except OSError:
            pass
        _server_socket = None
    if _listener_thread is not None:
        _listener_thread.join(timeout=2.0)
        _listener_thread = None


def is_running():
    return _listener_thread is not None and _listener_thread.is_alive()
