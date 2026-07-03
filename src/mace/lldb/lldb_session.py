"""
MACE — Mobile AArch64 Context Extension
lldb/lldb_session.py

Bridges the LLDB Python API to ContextSnapshot.
Reads live register state from a stopped process and returns a populated snapshot.
"""

import lldb
from mace.core.context_snapshot import ContextSnapshot


def _read_gpr(frame: lldb.SBFrame, name: str) -> int:
    """Read a named general purpose register as a Python int."""
    reg = frame.FindRegister(name)
    if reg.IsValid():
        return reg.GetValueAsUnsigned(0)
    return 0


def _detect_stripped(target: lldb.SBTarget) -> bool:
    """
    Heuristic: binary is considered stripped if the main module
    has no function symbols beyond _start / main.
    """
    module = target.GetModuleAtIndex(0)
    if not module.IsValid():
        return False
    sym_count = module.GetNumSymbols()
    # Stripped binaries typically have very few or no debug symbols
    return sym_count < 5


def snapshot_from_frame(frame: lldb.SBFrame,
                         stop_reason: str = "",
                         iteration: int = None) -> ContextSnapshot:
    """
    Build a ContextSnapshot from a live LLDB SBFrame.
    Call this inside a stop hook or breakpoint callback.
    """
    snap = ContextSnapshot()

    # --- General purpose registers x0–x28 ---
    for i in range(29):
        snap.x[i] = _read_gpr(frame, f"x{i}")

    # --- Special registers ---
    snap.fp   = _read_gpr(frame, "fp")
    snap.lr   = _read_gpr(frame, "lr")
    snap.sp   = _read_gpr(frame, "sp")
    snap.pc   = _read_gpr(frame, "pc")
    snap.cpsr = _read_gpr(frame, "cpsr")

    # --- Metadata ---
    target = frame.GetThread().GetProcess().GetTarget()
    module = target.GetModuleAtIndex(0)

    snap.binary_name = module.GetFileSpec().GetFilename() if module.IsValid() else "unknown"
    snap.is_stripped = _detect_stripped(target)
    snap.stop_reason = stop_reason or _get_stop_reason(frame.GetThread())
    snap.iteration   = iteration

    return snap


def _get_stop_reason(thread: lldb.SBThread) -> str:
    """Translate LLDB stop reason enum to a human-readable string."""
    reason = thread.GetStopReason()
    mapping = {
        lldb.eStopReasonBreakpoint:  "breakpoint",
        lldb.eStopReasonWatchpoint:  "watchpoint",
        lldb.eStopReasonSignal:      "signal",
        lldb.eStopReasonPlanComplete: "step",
        lldb.eStopReasonException:   "exception",
    }
    return mapping.get(reason, "unknown")
