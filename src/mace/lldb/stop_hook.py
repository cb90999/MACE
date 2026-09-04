"""
MACE — Mobile AArch64 Context Extension
lldb/stop_hook.py
"""

import lldb
import sys
import re
import time

from mace.lldb.lldb_session import snapshot_from_frame, _get_breakpoint_id
from mace.display.context_panel import render_panel, Color

WATCH_REGS = [0, 1]
COMPARE    = None  # set per-session

_iteration = 0
_hook_id   = None

# In-session patch audit trail. Persists for the life of the lldb
# session (not tied to any single breakpoint or stop-hook iteration),
# so a full bypass sequence's patches can be reviewed/exported at the
# end via mace_patch_history.
_patch_history: list[dict] = []

# In-session hardware-breakpoint audit trail, same lifecycle/purpose
# as _patch_history above.
_hw_break_history: list[dict] = []

# In-session snapshot history — every ContextSnapshot built while
# mace_on is active, kept for mace_search. Previously each snapshot
# was rendered once and discarded; this is what lets mace_search ask
# "did this address/name show up at an earlier stop" without the
# user having to scroll back through (or paste) raw panel output.
_snapshot_history: list = []


class MACEStopHook:
    def __init__(self, target, extra_args, internal_dict):
        self.target = target

    def handle_stop(self, exe_ctx, stream):
        global _iteration

        thread = exe_ctx.GetThread()

        # Skip signal stops (dyld entry, etc.)
        if thread.GetStopReason() == lldb.eStopReasonSignal:
            return False

        _iteration += 1
        frame = thread.GetFrameAtIndex(0)

        if not frame.IsValid():
            return False

        snap  = snapshot_from_frame(frame, iteration=_iteration)
        _snapshot_history.append(snap)
        panel = render_panel(snap, watch=WATCH_REGS, compare=COMPARE)
        stream.Print(panel + "\n")
        return True


def mace_on(debugger, command, result, internal_dict):
    """Enable MACE context panel on every stop."""
    global _hook_id, _iteration
    _iteration = 0
    debugger.HandleCommand("target stop-hook add -P stop_hook.MACEStopHook")
    print("[MACE] Context panel enabled. x0/x1 watched.")


def mace_off(debugger, command, result, internal_dict):
    """Disable MACE context panel."""
    debugger.HandleCommand("target stop-hook disable")
    print("[MACE] Context panel disabled.")


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f stop_hook.mace_on mace_on")
    debugger.HandleCommand("command script add -f stop_hook.mace_off mace_off")
    debugger.HandleCommand("command script add -c stop_hook.MACESwiftLoad mace_swift_load")
    debugger.HandleCommand("command script add -c stop_hook.MACEPatch mace_patch")
    debugger.HandleCommand("command script add -c stop_hook.MACEPatchHistory mace_patch_history")
    debugger.HandleCommand("command script add -c stop_hook.MACEGrep mace_grep")
    debugger.HandleCommand("command script add -c stop_hook.MACESearch mace_search")
    debugger.HandleCommand("command script add -c stop_hook.MACEHwBreak mace_hw_break")
    debugger.HandleCommand("command script add -c stop_hook.MACEHwBreakHistory mace_hw_break_history")
    print("[MACE] Loaded. Use 'mace_on' after setting breakpoints to enable.")

class MACESwiftLoad:
    """mace_swift_load <path> — load Swift type context from local binary path."""

    def __init__(self, debugger, internal_dict):
        pass

    def __call__(self, debugger, command, exe_ctx, result, internal_dict=None):
        path = command.strip().strip('"').strip("'")
        if not path:
            result.AppendMessage("[MACE] Usage: mace_swift_load <path_to_binary>")
            return
        import os
        from mace.core.swift_context import SwiftContext
        from mace.lldb.lldb_session import _swift_context_cache
        ctx = SwiftContext(path, exe_ctx=exe_ctx)
        if ctx.is_loaded():
            _swift_context_cache[path] = ctx
            _swift_context_cache[os.path.basename(path)] = ctx
            result.AppendMessage(f"[MACE] Swift context loaded: {len(ctx.all_types())} types from {os.path.basename(path)}")
            if ctx.resolved_path:
                result.AppendMessage(f"[MACE]   note: device path not found locally — auto-resolved to {ctx.resolved_path}")
            for t in ctx.all_types()[:5]:
                result.AppendMessage(f"  {t}")
        else:
            result.AppendMessage(f"[MACE] Failed to load Swift context from {path}")
            if ctx.load_error:
                result.AppendMessage(f"[MACE]   reason: {ctx.load_error}")

    def get_short_help(self):
        return "Load Swift type context from a local binary path"


class MACEPatch:
    """
    mace_patch <register> <value> — write a register via LLDB's SBValue
    API (not the raw `register write` command text), guarded against
    patching a process that isn't stopped, with every successful write
    recorded to the mace_patch_history audit trail.

    Examples:
      mace_patch x0 1
      mace_patch w0 0x1
    """

    def __init__(self, debugger, internal_dict):
        pass

    def __call__(self, debugger, command, exe_ctx, result, internal_dict=None):
        parts = command.strip().split()
        if len(parts) != 2:
            result.AppendMessage("[MACE] Usage: mace_patch <register> <value>")
            result.AppendMessage("[MACE]   e.g. mace_patch x0 1")
            result.AppendMessage("[MACE]        mace_patch w0 0x1")
            return

        reg_name, value_str = parts

        process = exe_ctx.GetProcess()
        if not process.IsValid() or process.GetState() != lldb.eStateStopped:
            result.AppendMessage(
                "[MACE] Cannot patch — process is not stopped. "
                "Continue (c) until you hit a breakpoint, then patch."
            )
            return

        thread = exe_ctx.GetThread()
        frame = exe_ctx.GetFrame()
        if not frame.IsValid():
            result.AppendMessage("[MACE] Cannot patch — no valid stack frame.")
            return

        reg_value = frame.FindRegister(reg_name)
        if not reg_value.IsValid():
            result.AppendMessage(f"[MACE] Unknown register '{reg_name}'.")
            return

        try:
            new_value = int(value_str, 0)  # accepts decimal or 0x-prefixed hex
        except ValueError:
            result.AppendMessage(f"[MACE] Could not parse value '{value_str}' as an integer.")
            return

        old_value = reg_value.GetValueAsUnsigned()

        error = lldb.SBError()
        reg_value.SetValueFromCString(f"0x{new_value:x}", error)
        if not error.Success():
            result.AppendMessage(f"[MACE] Patch failed: {error.GetCString()}")
            return

        # Read back to confirm the write actually took, rather than
        # trusting SetValueFromCString's success flag alone.
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
        _patch_history.append(record)

        bp_str = f" (breakpoint {bp_id})" if bp_id else ""
        result.AppendMessage(
            f"[MACE] {reg_name}: 0x{old_value:x} -> 0x{confirmed_value:x}"
            f"  at 0x{pc:x} in {func_name}{bp_str}"
        )
        if confirmed_value != new_value:
            result.AppendMessage(
                f"[MACE]   warning: requested 0x{new_value:x} but register "
                f"reads back as 0x{confirmed_value:x} — write may have been "
                f"truncated to the register's actual width."
            )

    def get_short_help(self):
        return "Patch a register via SBValue API; records to mace_patch_history"


class MACEPatchHistory:
    """
    mace_patch_history — show every mace_patch write applied this
    session, in order. `mace_patch_history clear` resets the log.
    """

    def __init__(self, debugger, internal_dict):
        pass

    def __call__(self, debugger, command, exe_ctx, result, internal_dict=None):
        arg = command.strip()

        if arg == "clear":
            count = len(_patch_history)
            _patch_history.clear()
            result.AppendMessage(f"[MACE] Patch history cleared ({count} entries removed).")
            return

        if not _patch_history:
            result.AppendMessage("[MACE] No patches applied yet this session.")
            return

        result.AppendMessage(f"{Color.BOLD}── MACE patch history ──{Color.RESET}")
        for i, rec in enumerate(_patch_history, 1):
            bp_str = f"  breakpoint {rec['breakpoint_id']}" if rec['breakpoint_id'] else ""
            result.AppendMessage(
                f"  {Color.WHITE}[{i}]{Color.RESET}  {rec['timestamp']}  "
                f"{rec['register']}: 0x{rec['old_value']:x} -> 0x{rec['new_value']:x}"
                f"  at 0x{rec['pc']:x} in {rec['function']}{bp_str}"
            )

    def get_short_help(self):
        return "Show (or clear) the mace_patch audit trail for this session"


class MACEGrep:
    """
    mace_grep <pattern> <lldb_command> — run any lldb command internally
    and print only the lines matching <pattern> (regex, case-insensitive),
    instead of the full raw output. Fixes the "paste a 700-line dump into
    chat" problem — filter before it ever prints.

    The inner command runs exactly as if typed directly (same target/
    process/thread/frame context); only its output is intercepted.

    Examples:
      mace_grep DVIA "image list -o -f"
      mace_grep objc_msgSend "disassemble -c 40"
      mace_grep jailbreak "image lookup -rn jailbreak"
    """

    def __init__(self, debugger, internal_dict):
        pass

    def __call__(self, debugger, command, exe_ctx, result, internal_dict=None):
        parts = command.strip().split(None, 1)
        if len(parts) != 2:
            result.AppendMessage("[MACE] Usage: mace_grep <pattern> <lldb_command>")
            result.AppendMessage('[MACE]   e.g. mace_grep DVIA "image list -o -f"')
            return

        pattern, inner_command = parts
        inner_command = inner_command.strip().strip('"').strip("'")

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            result.AppendMessage(f"[MACE] Invalid pattern '{pattern}': {e}")
            return

        inner_result = lldb.SBCommandReturnObject()
        interpreter = debugger.GetCommandInterpreter()
        # Two-arg form: runs against the debugger's currently selected
        # target/process/thread/frame, same as typing the command
        # directly at the prompt — no separate exe_ctx threading needed.
        interpreter.HandleCommand(inner_command, inner_result)

        output = inner_result.GetOutput() or ""
        error_output = inner_result.GetError() or ""

        if not inner_result.Succeeded() and not output:
            result.AppendMessage(
                f"[MACE] Command failed: {error_output.strip() or '(no output)'}"
            )
            return

        lines = output.splitlines()
        matches = [line for line in lines if regex.search(line)]

        if not matches:
            result.AppendMessage(
                f"[MACE] No matches for '{pattern}' in {len(lines)} lines of output."
            )
            return

        result.AppendMessage(
            f"[MACE] {len(matches)} of {len(lines)} lines match '{pattern}':"
        )
        for line in matches:
            result.AppendMessage(f"  {line}")

    def get_short_help(self):
        return "Run an lldb command, show only lines matching a pattern"


class MACESearch:
    """
    mace_search <0xADDRESS | substring> — search every stop recorded
    this session (while mace_on was active) for a register holding a
    specific address, or an objc/swift/function-name annotation
    containing a substring. Answers "did this show up before" without
    scrolling back through, or pasting, prior panel output.

    Address form matches any of x0-x28, fp, lr, sp, pc exactly.
    String form matches (case-insensitive) against the objc receiver/
    selector, swift_location, binary_name, or stop_reason recorded at
    that stop.

    Examples:
      mace_search 0x92e875b00
      mace_search NSFileManager
      mace_search jailbreakTest2
    """

    def __init__(self, debugger, internal_dict):
        pass

    def __call__(self, debugger, command, exe_ctx, result, internal_dict=None):
        query = command.strip()
        if not query:
            result.AppendMessage("[MACE] Usage: mace_search <0xADDRESS | substring>")
            result.AppendMessage("[MACE]   e.g. mace_search 0x92e875b00")
            result.AppendMessage("[MACE]        mace_search NSFileManager")
            return

        if not _snapshot_history:
            result.AppendMessage(
                "[MACE] No stops recorded yet this session. mace_search only "
                "searches stops that happened while mace_on was active."
            )
            return

        addr_query = None
        try:
            addr_query = int(query, 0)
        except ValueError:
            pass

        matches = []
        if addr_query is not None:
            for snap in _snapshot_history:
                hits = [f"x{i}" for i in range(29) if snap.x[i] == addr_query]
                if snap.fp == addr_query:
                    hits.append("fp")
                if snap.lr == addr_query:
                    hits.append("lr")
                if snap.sp == addr_query:
                    hits.append("sp")
                if snap.pc == addr_query:
                    hits.append("pc")
                if hits:
                    matches.append((snap, hits))
        else:
            needle = query.lower()
            for snap in _snapshot_history:
                haystack = " ".join(filter(None, [
                    snap.objc_receiver, snap.objc_selector,
                    snap.swift_location, snap.binary_name, snap.stop_reason,
                ])).lower()
                if needle in haystack:
                    matches.append((snap, []))

        if not matches:
            result.AppendMessage(
                f"[MACE] No matches for '{query}' across "
                f"{len(_snapshot_history)} recorded stops."
            )
            return

        result.AppendMessage(
            f"[MACE] {len(matches)} of {len(_snapshot_history)} stops match '{query}':"
        )
        for snap, hits in matches:
            bp_str = f"breakpoint {snap.breakpoint_id}" if snap.breakpoint_id else snap.stop_reason
            where = snap.swift_location or (
                f"{snap.objc_receiver} {snap.objc_selector}".strip()
                if (snap.objc_receiver or snap.objc_selector) else ""
            )
            where_str = f"  in {where}" if where else ""
            reg_str = f"  [{', '.join(hits)}]" if hits else ""
            result.AppendMessage(
                f"  [stop #{snap.iteration}]  {bp_str}  pc=0x{snap.pc:x}"
                f"{where_str}{reg_str}"
            )

    def get_short_help(self):
        return "Search all recorded stops this session for an address or annotation string"


class MACEHwBreak:
    """
    mace_hw_break <address> [<module>] — set a hardware breakpoint
    (CPU debug register, no memory write) at a given address, optionally
    scoped to a specific module (file-relative offset, resolved the
    same way as `breakpoint set -a <addr> --shlib <module>` -- lldb
    handles the ASLR-slide math, MACE doesn't reimplement it).

    Motivating use case: a target that self-checks its own code for
    tampering (a software breakpoint writes a trap byte into the
    target's own __TEXT section; a hardware breakpoint writes nothing
    to memory at all, so a checksum/integrity check over the code
    can't observe it).

    Built via `breakpoint set ... -H` through the command interpreter
    (same pattern as mace_grep), not a direct SBBreakpoint Python API
    call -- LLDB's Python API doesn't expose a clean, well-documented
    "make this hardware" method the way SBValue's register-write API
    does for mace_patch, so this goes through the interpreter rather
    than guess at an uncertain API surface.

    Verifies genuine hardware backing after creation by checking
    `breakpoint list`'s own status text for the literal word "hardware"
    -- confirmed live 2026-09-05 (mach_msg2_trap, DVIA-v2 session) that
    lldb prints this next to a location that's actually CPU-debug-
    register backed, distinct from a location that silently fell back
    to software (e.g. if hardware debug register slots -- ARM typically
    has only a handful -- were exhausted). Not a Python-API-level
    guarantee (LLDB's SB API has no direct IsHardware() the way
    SBValue's register-write API supports mace_patch's readback
    confirmation), so this is a text-based check on real, observed
    output, not a documented API contract -- worth re-confirming if a
    future LLDB/debugserver version changes this wording.

    Examples:
      mace_hw_break 0x1e8a84bf0
      mace_hw_break 0x100005564 "UnCrackable Level 2"
    """

    def __init__(self, debugger, internal_dict):
        pass

    def __call__(self, debugger, command, exe_ctx, result, internal_dict=None):
        parts = command.strip().split(None, 1)
        if not parts:
            result.AppendMessage("[MACE] Usage: mace_hw_break <address> [<module>]")
            result.AppendMessage("[MACE]   e.g. mace_hw_break 0x1e8a84bf0")
            result.AppendMessage('[MACE]        mace_hw_break 0x100005564 "UnCrackable Level 2"')
            return

        addr_str = parts[0]
        module = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else None

        try:
            addr = int(addr_str, 0)
        except ValueError:
            result.AppendMessage(f"[MACE] Could not parse '{addr_str}' as an address.")
            return

        inner_command = f"breakpoint set -a 0x{addr:x} -H"
        if module:
            inner_command += f' --shlib "{module}"'

        inner_result = lldb.SBCommandReturnObject()
        interpreter = debugger.GetCommandInterpreter()
        interpreter.HandleCommand(inner_command, inner_result)

        output = (inner_result.GetOutput() or "").strip()
        error_output = (inner_result.GetError() or "").strip()

        if not inner_result.Succeeded():
            result.AppendMessage(f"[MACE] Hardware breakpoint set failed: {error_output or '(no output)'}")
            return

        # Extract the breakpoint ID lldb assigned, same light text-parse
        # approach mace_grep already uses on interpreter output.
        bp_id_match = re.search(r"Breakpoint (\d+):", output)
        bp_id = bp_id_match.group(1) if bp_id_match else "?"

        # Verify genuine hardware backing by checking `breakpoint list`'s
        # own status text — None means verification couldn't be attempted
        # (e.g. bp_id didn't parse, or the list command itself failed),
        # distinct from True/False (a real, observed result either way).
        hardware_confirmed = None
        if bp_id != "?":
            list_result = lldb.SBCommandReturnObject()
            interpreter.HandleCommand(f"breakpoint list {bp_id}", list_result)
            if list_result.Succeeded():
                list_output = (list_result.GetOutput() or "")
                hardware_confirmed = "hardware" in list_output.lower()

        record = {
            "address":            addr,
            "module":             module or "",
            "bp_id":              bp_id,
            "raw_output":         output,
            "hardware_confirmed": hardware_confirmed,
            "timestamp":          time.strftime("%H:%M:%S"),
        }
        _hw_break_history.append(record)

        result.AppendMessage(f"[MACE] Hardware breakpoint {bp_id} requested at 0x{addr:x}")
        result.AppendMessage(f"[MACE]   {output}")
        if hardware_confirmed is True:
            result.AppendMessage(
                "[MACE]   confirmed hardware-backed (verified via breakpoint list)."
            )
        elif hardware_confirmed is False:
            result.AppendMessage(
                "[MACE]   warning: breakpoint list does not show 'hardware' "
                "for this location — may have silently fallen back to "
                "software (e.g. hardware debug register slots exhausted). "
                "Treat as software-backed unless investigated further."
            )
        else:
            result.AppendMessage(
                "[MACE]   note: could not verify hardware backing "
                "(breakpoint list check failed) — genuine hardware backing "
                "is not independently confirmed."
            )

    def get_short_help(self):
        return "Set a hardware breakpoint (CPU debug register, no memory write); records to mace_hw_break_history"


class MACEHwBreakHistory:
    """
    mace_hw_break_history — show every mace_hw_break request applied
    this session, in order. `mace_hw_break_history clear` resets the
    log.
    """

    def __init__(self, debugger, internal_dict):
        pass

    def __call__(self, debugger, command, exe_ctx, result, internal_dict=None):
        arg = command.strip()

        if arg == "clear":
            count = len(_hw_break_history)
            _hw_break_history.clear()
            result.AppendMessage(f"[MACE] Hardware breakpoint history cleared ({count} entries removed).")
            return

        if not _hw_break_history:
            result.AppendMessage("[MACE] No hardware breakpoints requested yet this session.")
            return

        result.AppendMessage(f"{Color.BOLD}── MACE hardware breakpoint history ──{Color.RESET}")
        for i, rec in enumerate(_hw_break_history, 1):
            mod_str = f"  in {rec['module']}" if rec['module'] else ""
            hw_confirmed = rec.get('hardware_confirmed')  # older records may predate this field
            if hw_confirmed is True:
                hw_str = f"  {Color.GREEN}[hw confirmed]{Color.RESET}"
            elif hw_confirmed is False:
                hw_str = f"  {Color.YELLOW}[hw NOT confirmed]{Color.RESET}"
            else:
                hw_str = "  [hw unverified]"
            result.AppendMessage(
                f"  {Color.WHITE}[{i}]{Color.RESET}  {rec['timestamp']}  "
                f"breakpoint {rec['bp_id']}  at 0x{rec['address']:x}{mod_str}{hw_str}"
            )

    def get_short_help(self):
        return "Show (or clear) the mace_hw_break audit trail for this session"
