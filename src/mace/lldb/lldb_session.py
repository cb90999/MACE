"""
MACE — Mobile AArch64 Context Extension
lldb/lldb_session.py

Bridges the LLDB Python API to ContextSnapshot.
Reads live register state from a stopped process and returns a populated snapshot.
"""

import lldb
from mace.core.context_snapshot import ContextSnapshot
from mace.core.swift_context import SwiftContext

# Module-level Swift context cache — loaded once per binary
_swift_context_cache: dict[str, SwiftContext] = {}


def _get_swift_context(binary_path: str) -> SwiftContext:
    """Return cached SwiftContext for binary_path."""
    if binary_path not in _swift_context_cache:
        _swift_context_cache[binary_path] = SwiftContext(binary_path)
    return _swift_context_cache[binary_path]


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
    snap.breakpoint_id = _get_breakpoint_id(frame.GetThread())
    snap.iteration   = iteration
    snap.aslr_slide  = _compute_aslr_slide(target)

    # --- Passive objc_msgSend annotation ---
    _annotate_objc_call(snap, frame, target)

    # --- Swift "you are here" annotation ---
    # Independent of objc_msgSend detection — populates whenever Swift
    # context is loaded and the current frame's function name resolves,
    # e.g. mid-function stops from `finish`/`step` that aren't at a
    # message-send call site at all.
    _annotate_swift_location(snap, frame)

    # --- Passive syscall annotation ---
    # Independent of objc/Swift — populates whenever the current stop
    # happens to land directly on a real "svc #0x80" instruction,
    # whatever the reason for the stop (breakpoint, single-step, or
    # otherwise). Doesn't require a breakpoint placed on the syscall
    # itself — recognizes it wherever it's encountered.
    _annotate_syscall(snap, frame, target)

    return snap

def _annotate_swift_location(snap, frame) -> None:
    """
    "You are here" Swift annotation — independent of objc_msgSend detection.
    Resolves the current frame's function name against any loaded
    SwiftContext, so mid-function stops (finish/step, breakpoints not
    at a message-send site) still show which Swift type/method you're
    actually stopped inside.
    """
    try:
        func_name = frame.GetFunctionName() or ""
        if not func_name:
            return
        for ctx in _swift_context_cache.values():
            if not ctx.is_loaded():
                continue
            type_name = ctx.type_for_function(func_name)
            selector = ctx.selector_for_function(func_name)
            if type_name and selector:
                snap.swift_location = f"{type_name}.{selector}"
                return
            elif type_name:
                snap.swift_location = type_name
                return
    except Exception:
        pass  # Annotation is best-effort, never crash MACE


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


def _get_breakpoint_id(thread: lldb.SBThread) -> str:
    """
    Return "breakpoint_id.location_id" (e.g. "2.1") when the stop reason
    is a breakpoint hit, matching the format LLDB itself prints
    ("stop reason = breakpoint 2.1"). Returns "" otherwise, or if the
    breakpoint has multiple hit locations and we can't disambiguate.
    """
    try:
        if thread.GetStopReason() != lldb.eStopReasonBreakpoint:
            return ""
        bp_id  = thread.GetStopReasonDataAtIndex(0)
        loc_id = thread.GetStopReasonDataAtIndex(1)
        return f"{bp_id}.{loc_id}"
    except Exception:
        return ""


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


def _is_objc_msgsend_call_site(frame, target) -> bool:
    """
    Confirm the instruction at the current pc is a direct branch (bl)
    into an objc_msgSend-family stub, before trusting x0/x1 as a
    receiver/selector pair.

    Without this check, _annotate_objc_call fired on ANY stop where a
    register happened to look pointer-shaped (> 0x100000000) — including
    plain function entries with no message-send anywhere nearby —
    producing misattributed output: a real UIViewController pointer
    decoded as garbled "selector" text, or a real-but-wrong selector
    name (e.g. "class") attributed to a completely unrelated call.
    Found 2026-08-27, DVIA-v2 session; see BACKLOG.md.

    This codifies the exact pattern already proven correct in practice
    throughout this project: every time a breakpoint was deliberately
    set AT the "bl ... ; symbol stub for: objc_msgSend" instruction
    itself (not before or after it), the resulting annotation was
    correct. This function makes that condition an explicit,
    enforced gate instead of implicit practitioner knowledge.

    Only handles the direct-bl case — the overwhelming common case for
    Swift/ObjC message sends, which resolve through a dyld stub at a
    statically-known address (visible in disassembly as the trailing
    "; symbol stub for: objc_msgSend" comment). Indirect calls (blr,
    where the target is only known at runtime via a register) are not
    resolved — annotation is skipped rather than guessed at, matching
    the "fail safe, not silently wrong" principle this fix exists for.
    """
    try:
        pc_addr = frame.GetPCAddress()
        instructions = target.ReadInstructions(pc_addr, 1)
        if instructions.GetSize() == 0:
            return False
        insn = instructions.GetInstructionAtIndex(0)
        mnemonic = (insn.GetMnemonic(target) or "").lower()
        if mnemonic != "bl":
            return False
        comment = (insn.GetComment(target) or "").lower()
        return "objc_msgsend" in comment
    except Exception:
        return False


def _annotate_objc_call(snap, frame, target) -> None:
    """
    Passive objc_msgSend annotation - caller filtered.
    Only annotates when stopped directly at a real objc_msgSend-family
    call site (see _is_objc_msgsend_call_site) AND lr falls within the
    app's own __text section (skips Foundation/UIKit/system-internal
    message sends automatically). No global breakpoint needed - reads
    state at whatever stop already happened.
    """
    try:
        if not _is_objc_msgsend_call_site(frame, target):
            return  # not actually at a message-send call — nothing to annotate

        # Caller filter - only annotate app-owned ObjC calls
        ranges = _get_app_text_ranges(target)
        lr = snap.lr
        if ranges:
            if not any(s <= lr <= e for s, e in ranges):
                return  # caller is system/framework code, skip silently

        # Resolve receiver from x0
        x0 = snap.x[0]
        # Skip stack addresses (0x16xxxxxxxx on iOS) — not object pointers
        # TODO: generalize before merge — this range and the 0x100000000
        # pointer-vs-small-int threshold below are both empirical guesses
        # from observed addresses on one palera1n iPad/iOS 18.7.2 session,
        # not a documented ABI guarantee. Will silently mis-annotate (or
        # fail to annotate) on a different device, iOS version, or ASLR
        # layout. Replace with SBProcess.GetMemoryRegionInfo()-based
        # region classification — see BACKLOG.md Context Panel v2.
        # Note: now gated behind _is_objc_msgsend_call_site above, so
        # this heuristic only ever runs at a confirmed real call site —
        # its remaining risk is misclassifying x0 there, not misfiring
        # on unrelated stops (that failure mode is fixed by this change).
        if x0 and x0 > 0x100000000 and not (0x160000000 <= x0 <= 0x17fffffff):
            # Try ObjC runtime first
            expr_result = frame.EvaluateExpression(
                f"(const char *)object_getClassName((id){x0})"
            )
            if expr_result.IsValid() and not expr_result.GetError().Fail():
                val = expr_result.GetSummary()
                if val:
                    snap.objc_receiver = val.strip('"')

            # Fall back to SwiftContext if ObjC lookup failed
            if not snap.objc_receiver:
                # Use LLDB frame function name for precise Swift type resolution
                func_name = frame.GetFunctionName() or ""
                for key, ctx in _swift_context_cache.items():
                    if ctx.is_loaded():
                        # Try precise function-based lookup first
                        result = ctx.type_for_function(func_name)
                        if not result:
                            # Fall back to binary name matching
                            result = ctx.type_for_address(snap.binary_name or "")
                        if result:
                            snap.objc_receiver = result
                            # Also resolve selector from function name
                            if not snap.objc_selector:
                                sel = ctx.selector_for_function(func_name)
                                if sel:
                                    snap.objc_selector = sel
                            break

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



def _is_syscall_site(frame, target) -> bool:
    """
    Confirm the instruction at the current pc is a raw "svc #0x80" —
    the single trap instruction AArch64/XNU uses for BOTH BSD syscalls
    and Mach traps, distinguished only by the sign of x16 at the moment
    of the trap (positive = BSD syscall number, negative = Mach trap
    number). Confirmed live 2026-08-30: libsystem_kernel.dylib's
    macx_swapon uses "mov x16, #-0x30 ; svc #0x80" — a Mach trap, not
    a BSD syscall, at the exact same instruction shape.

    Same gating pattern as _is_objc_msgsend_call_site: confirm the
    real instruction before trusting any register as syscall content,
    rather than inferring from register values alone.
    """
    try:
        pc_addr = frame.GetPCAddress()
        instructions = target.ReadInstructions(pc_addr, 1)
        if instructions.GetSize() == 0:
            return False
        insn = instructions.GetInstructionAtIndex(0)
        mnemonic = (insn.GetMnemonic(target) or "").lower()
        if mnemonic != "svc":
            return False
        operands = (insn.GetOperands(target) or "").lower()
        return "0x80" in operands
    except Exception:
        return False


# Best-effort syscall number -> name tables. Deliberately small and
# conservative: only numbers that are well-established and stable
# across iOS/macOS releases are included. An unrecognized number is
# shown as-is ("syscall #113" / "trap #103") rather than guessed —
# same "fail safe, not silently wrong" principle as the objc_msgSend
# call-site fix. Extend against XNU's actual source
# (bsd/kern/syscalls.master, osfmk/mach/syscall_sw.h) when adding
# entries, not from memory alone — an incorrect name here is worse
# than an honest "unrecognized number".
BSD_SYSCALLS = {
    1: "exit", 2: "fork", 3: "read", 4: "write", 5: "open", 6: "close",
    7: "wait4", 9: "link", 10: "unlink", 12: "chdir", 15: "chmod",
    16: "chown", 20: "getpid", 23: "setuid", 24: "getuid", 26: "ptrace",
    33: "access", 36: "sync", 37: "kill", 41: "dup", 42: "pipe",
    43: "getegid", 46: "sigaction", 47: "getgid", 54: "ioctl",
    57: "symlink", 58: "readlink", 59: "execve", 60: "umask",
    73: "munmap", 74: "mprotect", 75: "madvise", 90: "dup2", 92: "fcntl",
    93: "select", 97: "socket", 98: "connect", 104: "bind", 106: "listen",
    116: "gettimeofday", 117: "getrusage", 188: "stat", 189: "fstat",
    190: "lstat", 197: "mmap", 202: "sysctl",
}

MACH_TRAPS = {
    27: "thread_self_trap", 28: "task_self_trap", 29: "host_self_trap",
    31: "mach_msg_trap", 33: "semaphore_signal_trap",
    36: "semaphore_wait_trap", 45: "task_for_pid",
}


def _annotate_syscall(snap, frame, target) -> None:
    """
    Passive syscall annotation — decodes the pending BSD syscall or
    Mach trap whenever stopped directly at a real "svc #0x80"
    instruction (see _is_syscall_site). Unlike objc annotation, this
    doesn't require a breakpoint placed on the syscall itself — it
    recognizes one wherever a stop happens to land on it, including
    mid single-step sequences.

    x16 at the trap holds the call number: positive for a BSD syscall,
    negative for a Mach trap (both trap through the identical
    instruction on AArch64/XNU — see _is_syscall_site). Unrecognized
    numbers are shown as-is rather than guessed.
    """
    try:
        if not _is_syscall_site(frame, target):
            return

        x16_reg = frame.FindRegister("x16")
        if not x16_reg.IsValid():
            return
        raw = x16_reg.GetValueAsUnsigned()
        # Reinterpret as signed 64-bit to recover the sign XNU relies on —
        # GetValueAsUnsigned() always returns the raw unsigned bit pattern.
        signed = raw - (1 << 64) if raw >= (1 << 63) else raw

        snap.syscall_number = signed
        if signed > 0:
            snap.syscall_kind = "BSD"
            snap.syscall_name = BSD_SYSCALLS.get(signed, f"syscall #{signed}")
        elif signed < 0:
            snap.syscall_kind = "Mach trap"
            snap.syscall_name = MACH_TRAPS.get(-signed, f"trap #{-signed}")
        else:
            snap.syscall_kind = ""
            snap.syscall_name = "syscall #0"
    except Exception:
        pass  # Annotation is best-effort, never crash MACE
