"""
MACE — Mobile AArch64 Context Extension
lldb/stop_hook.py
"""

import lldb
import sys

_MACE_SRC = "/Users/chidabangalore/Documents/MACE/src"
if _MACE_SRC not in sys.path:
    sys.path.insert(0, _MACE_SRC)

from mace.lldb.lldb_session import snapshot_from_frame
from mace.display.context_panel import render_panel

WATCH_REGS = [8, 9]
COMPARE    = (8, 9)

_iteration = 0


class MACEStopHook:
    def __init__(self, target, extra_args, internal_dict):
        self.target = target

    def handle_stop(self, exe_ctx, stream):
        global _iteration

        thread = exe_ctx.GetThread()

        # Skip signal stops (entry stop in dyld, etc.)
        if thread.GetStopReason() == lldb.eStopReasonSignal:
            return False

        _iteration += 1
        frame = thread.GetFrameAtIndex(0)

        if not frame.IsValid():
            return False

        snap  = snapshot_from_frame(frame, iteration=_iteration)
        panel = render_panel(snap, watch=WATCH_REGS, compare=COMPARE)
        stream.Print(panel + "\n")
        return False


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(
        "target stop-hook add -P stop_hook.MACEStopHook"
    )
    print("[MACE] Stop hook installed.")
    print(f"[MACE] Watching: w{WATCH_REGS[0]}, w{WATCH_REGS[1]}  |  Compare: w{COMPARE[0]} vs w{COMPARE[1]}")
