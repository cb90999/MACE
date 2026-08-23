"""
MACE — Mobile AArch64 Context Extension
lldb/stop_hook.py
"""

import lldb
import sys
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
