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
    return sym_count < 5


def _compute_aslr_slide(target: lldb.SBTarget) -> int:
    """
    Compute ASLR slide for the main module.
    slide = load_address - file_address of the module header.
    Returns 0 if not computable (no ASLR, or module not loaded).
    """
    module = target.GetModuleAtIndex(0)
    if not module.IsValid():
        return 0

    obj_header = module.GetObjectFileHeaderAddress()
    file_addr = obj_header.GetFileAddress()
    load_addr = obj_header.GetLoadAddress(target)

    if load_addr == lldb.LLDB_INVALID_ADDRESS:
        return 0

    slide = load_addr - file_addr
    return slide if slide >= 0 else 0


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
    snap.aslr_slide  = _compute_aslr_slide(target)

    # --- Passive objc_msgSend annotation ---
    _annotate_objc_call(snap, frame, target)

    return snap


def _get_stop_reason(thread: lldb.SBThread) -> str:
    """Translate LLDB stop reason enum to a human-readable string."""
    reason = thread.GetStopReason()
    mapping = {
        lldb.eStopReasonBreakpoint:   "breakpoint",
        lldb.eStopReasonWatchpoint:   "watchpoint",
        lldb.eStopReasonSignal:       "signal",
        lldb.eStopReasonPlanComplete: "step",
        lldb.eStopReasonException:    "exception",
    }
    return mapping.get(reason, "unknown")


def _get_app_text_ranges(target) -> list:
    """
    Return list of (start, end) tuples for all app-owned __text sections.
    Includes main binary and embedded frameworks/dylibs.
    Excludes system libraries in /usr/lib, /System, /Library/Apple.
    """
    ranges = []
    try:
        system_prefixes = ("/usr/lib", "/System", "/Library/Apple",
                           "/private/preboot", "libsystem", "libobjc",
                           "CoreFoundation", "Foundation", "UIKit")
        for i in range(target.GetNumModules()):
            module = target.GetModuleAtIndex(i)
            if not module.IsValid():
                continue
            path = module.GetFileSpec().GetDirectory() or ""
            fname = module.GetFileSpec().GetFilename() or ""
            full = path + "/" + fname
            # Skip system libraries
            if any(p in full for p in system_prefixes):
                continue
            for j in range(module.GetNumSections()):
                section = module.GetSectionAtIndex(j)
                for k in range(section.GetNumSubSections()):
                    sub = section.GetSubSectionAtIndex(k)
                    if sub.GetName() == "__text":
                        start = sub.GetLoadAddress(target)
                        end = start + sub.GetByteSize()
                        if start != 0xffffffffffffffff:
                            ranges.append((start, end))
    except Exception:
        pass
    return ranges


def _get_app_text_range(target) -> tuple:
    """Legacy single-range interface — returns first app __text range."""
    ranges = _get_app_text_ranges(target)
    return ranges[0] if ranges else (0, 0)


def _annotate_objc_call(snap, frame, target) -> None:
    """
    Passive objc_msgSend annotation - caller filtered.
    Only annotates when lr falls within the app own __text section.
    Skips Foundation/UIKit/system calls automatically.
    No global breakpoint needed - reads state at existing stop.
    """
    try:
        # Caller filter - only annotate app-owned ObjC calls
        ranges = _get_app_text_ranges(target)
        lr = snap.lr
        if ranges:
            if not any(s <= lr <= e for s, e in ranges):
                return  # caller is system/framework code, skip silently

        # Resolve receiver from x0
        x0 = snap.x[0]
        if x0 and x0 > 0x100000000:
            expr_result = frame.EvaluateExpression(
                f"(const char *)object_getClassName((id){x0})"
            )
            if expr_result.IsValid() and not expr_result.GetError().Fail():
                val = expr_result.GetSummary()
                if val:
                    snap.objc_receiver = val.strip('"')

        # Resolve selector from x1
        x1 = snap.x[1]
        if x1 and x1 > 0x100000000:
            expr_result = frame.EvaluateExpression(
                f"(const char *)sel_getName((SEL){x1})"
            )
            if expr_result.IsValid() and not expr_result.GetError().Fail():
                val = expr_result.GetSummary()
                if val:
                    snap.objc_selector = val.strip('"')
    except Exception:
        pass  # Annotation is best-effort, never crash MACE
