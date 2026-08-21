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
    GREY    = "\033[90m"
    DIM     = "\033[2m"


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
        line += f"  {Color.DIM}w={w_val}{Color.RESET}"
    if ascii_val:
        line += f"  '{ascii_val}'"
    return line


def render_registers(snap: ContextSnapshot,
                     watch: Optional[list] = None) -> str:
    watch = watch or []
    lines = [_separator("registers")]

    for i in range(0, 29, 2):
        row = ""
        for j in [i, i + 1]:
            if j > 28:
                break
            hex_val  = snap.as_hex(j)
            decimal  = snap.as_decimal(j)
            ascii_v  = snap.as_ascii(j)
            highlight = j in watch
            w_val = snap.w_as_hex(j) if (snap.x[j] >> 32 == 0 and snap.x[j] != 0) else None
            row += _format_register_line(f"x{j}", hex_val, decimal, ascii_v, w_val, highlight)
            row += "    "
        lines.append(row)

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
    iter_tag = f"  iteration {snap.iteration}" if snap.iteration is not None else ""
    slide_tag = f"  {Color.DIM}slide=0x{snap.aslr_slide:016x}  offset=0x{snap.file_offset():08x}{Color.RESET}" if snap.aslr_slide != 0 else ""
    return (
        f"{Color.BOLD}── MACE{Color.RESET}  "
        f"{stripped_tag}"
        f"{Color.GREEN}{snap.binary_name}{Color.RESET}  "
        f"{Color.GREY}{snap.stop_reason}{iter_tag}{Color.RESET}"
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
    if snap.objc_receiver or snap.objc_selector:
        parts.append(_separator("objc"))
        receiver = snap.objc_receiver or "?"
        selector = snap.objc_selector or "?"
        parts.append(f"  {Color.CYAN}[{receiver} {selector}]{Color.RESET}")
    parts.append(Color.CYAN + "─" * width + Color.RESET)
    return "\n".join(parts)
