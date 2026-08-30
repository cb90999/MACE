"""
MACE — Mobile AArch64 Context Extension
display/context_panel.py
"""

import shutil
from typing import Optional
from mace.core.context_snapshot import ContextSnapshot


class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    # Intensity-based styles (bright-black/dim) are intentionally NOT
    # included here. They render at unreadable contrast on many terminal
    # themes (dark-on-dark, light-on-light) since "dim"/"faint" is a
    # relative adjustment the terminal applies to its own theme colors,
    # not a fixed color. Use the 8 standard ANSI hues above instead —
    # terminals remap those sensibly for whichever theme is active.


def _terminal_width() -> int:
    return shutil.get_terminal_size(fallback=(80, 24)).columns - 2


def _separator(label: str) -> str:
    width = _terminal_width()
    label_str = f"── {label} "
    remaining = width - len(label_str)
    return f"{Color.CYAN}{label_str}{'─' * max(remaining, 4)}{Color.RESET}"


def _format_register_line(name, hex_val, decimal, ascii_val, w_val, highlight=False):
    color = Color.YELLOW if highlight else Color.RESET
    line = f"  {color}{name:<6}{Color.RESET}  {hex_val}  # {decimal}u"
    if w_val is not None:
        line += f"  w={w_val}"
    if ascii_val:
        line += f"  '{ascii_val}'"
    return line


def render_registers(snap: ContextSnapshot,
                     watch: Optional[list] = None) -> str:
    watch = watch or []
    lines = [_separator("registers")]

    for j in range(29):
        hex_val  = snap.as_hex(j)
        decimal  = snap.as_decimal(j)
        ascii_v  = snap.as_ascii(j)
        highlight = j in watch
        w_val = snap.w_as_hex(j) if (snap.x[j] >> 32 == 0 and snap.x[j] != 0) else None
        lines.append(_format_register_line(f"x{j}", hex_val, decimal, ascii_v, w_val, highlight))

    lines.append("")
    lines.append(f"  {'fp':<6}  0x{snap.fp:016x}  # {snap.fp}u")
    lines.append(f"  {'lr':<6}  0x{snap.lr:016x}  # {snap.lr}u")
    lines.append(f"  {'sp':<6}  0x{snap.sp:016x}  # {snap.sp}u")
    lines.append(f"  {'pc':<6}  0x{snap.pc:016x}  # {snap.pc}u")
    # Decode CPSR condition flags
    cpsr = snap.cpsr
    n = (cpsr >> 31) & 1  # Negative
    z = (cpsr >> 30) & 1  # Zero
    c = (cpsr >> 29) & 1  # Carry
    v = (cpsr >> 28) & 1  # Overflow
    el = (cpsr >> 2) & 0x3  # Exception Level
    flags = f"[N={n} Z={z} C={c} V={v} EL={el}]"
    
    # Human-readable flag interpretation
    if z == 1 and n == 0:
        meaning = "last cmp: equal"
    elif n == 1 and v == 0:
        meaning = "last cmp: less than"
    elif n == 0 and v == 0:
        meaning = "last cmp: greater than"
    elif c == 1 and z == 0:
        meaning = "last cmp: unsigned higher"
    else:
        meaning = ""
    
    meaning_str = f"  # {meaning}" if meaning else ""
    lines.append(f"  {'cpsr':<6}  0x{snap.cpsr:08x}  {flags}{meaning_str}")

    return "\n".join(lines)


def render_stop_banner(snap: ContextSnapshot) -> str:
    stripped_tag = f"{Color.RED}[stripped]{Color.RESET} " if snap.is_stripped else ""

    # Show the actual breakpoint ID (e.g. "breakpoint 2.1") when available —
    # matches what LLDB's own "stop reason = breakpoint 2.1" line shows,
    # so the two outputs read consistently instead of MACE saying just
    # "breakpoint" with no way to tell which one fired.
    if snap.stop_reason == "breakpoint" and snap.breakpoint_id:
        reason_str = f"breakpoint {snap.breakpoint_id}"
    else:
        reason_str = snap.stop_reason

    # Iteration is a global stop counter across the whole session, not
    # tied to which breakpoint fired — useful for spotting loops, but
    # not the primary "where am I" signal, so it's demoted after the
    # reason rather than leading.
    iter_tag = f"  (stop #{snap.iteration})" if snap.iteration is not None else ""

    slide_tag = f"  slide=0x{snap.aslr_slide:016x}  offset=0x{snap.file_offset():08x}" if snap.aslr_slide != 0 else ""
    return (
        f"{Color.BOLD}── MACE{Color.RESET}  "
        f"{stripped_tag}"
        f"{Color.GREEN}{snap.binary_name}{Color.RESET}  "
        f"{Color.WHITE}{reason_str}{Color.RESET}"
        f"{iter_tag}"
        f"{slide_tag}"
    )


def render_match_status(snap: ContextSnapshot, a: int, b: int) -> str:
    va = snap.w(a)
    vb = snap.w(b)
    match = va == vb
    status = f"{Color.GREEN}MATCH{Color.RESET}" if match else f"{Color.RED}MISMATCH{Color.RESET}"
    delta  = "" if match else f"  delta=0x{abs(va - vb):08x}"
    return f"  w{a} vs w{b}  →  {status}{delta}"


def render_panel(snap: ContextSnapshot,
                 watch: Optional[list] = None,
                 compare: Optional[tuple] = None) -> str:
    width = _terminal_width()
    parts = [
        render_stop_banner(snap),
        render_registers(snap, watch=watch),
    ]
    if compare:
        parts.append(_separator("comparison"))
        parts.append(render_match_status(snap, *compare))
    if snap.swift_location:
        parts.append(_separator("swift"))
        parts.append(f"  {Color.CYAN}[{snap.swift_location}]{Color.RESET}")
    if snap.objc_receiver or snap.objc_selector:
        parts.append(_separator("objc"))
        receiver = snap.objc_receiver or "?"
        selector = snap.objc_selector or "?"
        parts.append(f"  {Color.CYAN}[{receiver} {selector}]{Color.RESET}")
    if snap.syscall_name:
        parts.append(_separator("syscall"))
        kind_tag = f"  ({snap.syscall_kind})" if snap.syscall_kind else ""
        parts.append(f"  {Color.CYAN}[{snap.syscall_name}]{Color.RESET}{kind_tag}")
    parts.append(Color.CYAN + "─" * width + Color.RESET)
    return "\n".join(parts)
