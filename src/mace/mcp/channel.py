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

Tool registry: a plain dict, name -> callable(debugger, args) -> JSON-
serializable result. Step 2 populates this with real mace_* tools;
this module ships with only "ping" registered, to validate the channel
end-to-end before any real tool is wired in.

Thread safety (known, documented limitation -- see BACKLOG.md): the
listener runs in a background thread, separate from lldb's own
stop-hook callback thread. Every tool-registry call is serialized
through LLDB_LOCK below, which prevents two concurrent MCP calls from
racing each other. It does NOT currently prevent a race between this
channel's thread and stop_hook.py's handle_stop -- that would require
sharing a single lock across both call sites, deferred as a scoped
decision for Dec (CB, 2026-11-03).
"""

import json
import os
import socket
import threading

LLDB_LOCK = threading.Lock()

_TOOLS = {}  # name -> callable(debugger, args) -> JSON-serializable result

_listener_thread = None
_server_socket = None
_shutdown = threading.Event()


def register_tool(name, fn):
    """Register a tool handler. fn(debugger, args) -> JSON-serializable result."""
    _TOOLS[name] = fn


def _handle_ping(debugger, args):
    return {"pong": True}


register_tool("ping", _handle_ping)


def _dispatch(debugger, request):
    tool = request.get("tool")
    args = request.get("args", {})
    if tool is None:
        return {"ok": False, "error": "request missing 'tool'"}
    handler = _TOOLS.get(tool)
    if handler is None:
        return {"ok": False, "error": f"unknown tool: {tool!r}"}
    try:
        with LLDB_LOCK:
            result = handler(debugger, args)
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
