"""
MACE — Mobile AArch64 Context Extension
lldb/trace_mode.py
"""

import lldb
import sys

_MACE_SRC = "/Users/chidabangalore/Documents/MACE/src"
if _MACE_SRC not in sys.path:
    sys.path.insert(0, _MACE_SRC)

from mace.lldb.lldb_session import snapshot_from_frame
from mace.display.context_panel import Color

_trace_log  = []
_watch_regs = [8, 9]
_compare    = (8, 9)
_iteration  = 0
_debugger   = None


def _trace_callback(frame, bp_loc, extra_args, internal_dict):
    global _iteration
    _iteration += 1

    snap = snapshot_from_frame(frame, iteration=_iteration)

    wa, wb = _compare
    va = snap.w(wa)
    vb = snap.w(wb)
    match = "✓" if va == vb else "✗"
    color = Color.GREEN if va == vb else Color.RED

    line = (
        f"  [{_iteration:>3}]  "
        f"w{wa}={snap.w_as_hex(wa)}  "
        f"w{wb}={snap.w_as_hex(wb)}  "
        f"{color}{match}{Color.RESET}  "
        f"pc=0x{snap.pc:016x}"
    )
    _trace_log.append(line)
    print(line)

    # Continue via debugger handle — avoids conflict with command list
    if _debugger:
        _debugger.HandleCommand("continue")

    return False


def mace_trace_on(debugger, command, result, internal_dict):
    global _iteration, _trace_log, _debugger
    _iteration = 0
    _trace_log = []
    _debugger  = debugger

    target = debugger.GetSelectedTarget()
    args = command.strip()
    bp_id = int(args) if args else target.GetNumBreakpoints()

    bp = target.FindBreakpointByID(bp_id)
    if not bp.IsValid():
        print(f"[MACE] Breakpoint {bp_id} not found.")
        return

    # Python callback only — no command list
    bp.SetScriptCallbackFunction("trace_mode._trace_callback")

    print(f"[MACE] Trace mode ON — breakpoint {bp_id}")
    print(f"[MACE] Watching w{_watch_regs[0]}, w{_watch_regs[1]}")
    print(f"{'─' * 64}")
    print(f"  {'[itr]':<7} w{_watch_regs[0]:<14} w{_watch_regs[1]:<14} {'ok':<4} pc")
    print(f"{'─' * 64}")


def mace_trace_off(debugger, command, result, internal_dict):
    print(f"\n{'─' * 64}")
    print(f"[MACE] Trace complete — {_iteration} iterations captured")
    matches = sum(1 for l in _trace_log if "✓" in l)
    print(f"[MACE] {matches}/{_iteration} comparisons matched")


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f trace_mode.mace_trace_on mace_trace_on")
    debugger.HandleCommand("command script add -f trace_mode.mace_trace_off mace_trace_off")
    print("[MACE] Trace mode loaded. Use 'mace_trace_on' after setting breakpoint.")
