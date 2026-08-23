"""
MACE — Mobile AArch64 Context Extension
lldb/stop_hook.py
"""

import lldb
import sys

from mace.lldb.lldb_session import snapshot_from_frame
from mace.display.context_panel import render_panel

WATCH_REGS = [0, 1]
COMPARE    = None  # set per-session

_iteration = 0
_hook_id   = None


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
