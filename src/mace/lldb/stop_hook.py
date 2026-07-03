"""
MACE — Mobile AArch64 Context Extension
lldb/stop_hook.py

LLDB stop hook — fires render_panel on every process stop.

Load into LLDB with:
    (lldb) command script import /path/to/src/mace/lldb/stop_hook.py
"""

import lldb
import sys
import os

# Ensure src/ is on the path when loaded from LLDB
_here = os.path.dirname(os.path.abspath(__file__))
_src  = os.path.abspath(os.path.join(_here, "..", "..", ".."))
if _src not in sys.path:
    sys.path.insert(0, _src)

from mace.lldb.lldb_session import snapshot_from_frame
from mace.display.context_panel import render_panel

# Registers to watch and compare — configure per session
WATCH_REGS  = [8, 9]      # highlight w8, w9
COMPARE     = (8, 9)      # show match/mismatch for w8 vs w9

# Loop iteration counter — increments on each stop
_iteration = 0


class MACEStopHook:
    """
    LLDB stop hook class.
    Registered via target stop-hook add --python-class stop_hook.MACEStopHook
    """

    def __init__(self, target, extra_args, internal_dict):
        self.target = target

    def handle_stop(self, exe_ctx, stream):
        global _iteration
        _iteration += 1

        thread = exe_ctx.GetThread()
        frame  = thread.GetFrameAtIndex(0)

        if not frame.IsValid():
            return False

        snap = snapshot_from_frame(
            frame,
            iteration=_iteration
        )

        panel = render_panel(snap, watch=WATCH_REGS, compare=COMPARE)
        stream.Print(panel + "\n")
        return False   # False = don't suppress default LLDB output


def __lldb_init_module(debugger, internal_dict):
    """Called by LLDB when the script is imported."""
    debugger.HandleCommand(
        "target stop-hook add --python-class stop_hook.MACEStopHook"
    )
    print("[MACE] Stop hook installed. Context panel will render on every stop.")
    print(f"[MACE] Watching: w{WATCH_REGS[0]}, w{WATCH_REGS[1]}  |  Compare: w{COMPARE[0]} vs w{COMPARE[1]}")
