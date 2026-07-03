"""
MACE — Mobile AArch64 Context Extension
display/context_panel.py

Renders the GEF-like context panel to the terminal on every LLDB stop.
Reads from a ContextSnapshot — no LLDB dependency here.
"""

from typing import Optional
from mace.core.context_snapshot import ContextSnapshot


# ANSI color codes
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    CYAN    = "\033[36m"
    GREY    = "\033[90m"


def _separator(label: str, width: int = 64) -> str:
    label_str = f"── {label} "
    remaining = width - len(label_str)
    return f"{Color.CYAN}{label_str}{'─' * remaining}{Color.RESET}"


def _format_register_line(name: str, hex_val: str, decimal: int,
                           ascii_val: Optional[str], highlight: bool = False) -> str:
    color = Color.YELLOW if highlight else Color.RESET
    line = f"  {color}{name:<6}{Color.RESET}  {hex_val}  # {decimal}u"
    if ascii_val:
        line += f"  '{ascii_val}'"
    return line


def render_registers(snap: ContextSnapshot,
                     watch: Optional[list[int]] = None) -> str:
    """
    Render the register panel.
    watch: list of xN indices to highlight (e.g. [8, 9] for EEA comparison)
    """
    watch = watch or []
    lines = [_separator("registers")]

    # General purpose x0–x28 in rows of 2
    for i in range(0, 29, 2):
        row = ""
        for j in [i, i + 1]:
            if j > 28:
                break
            hex_val  = snap.as_hex(j)
            decimal  = snap.as_decimal(j)
            ascii_v  = snap.as_ascii(j)
            highlight = j in watch
            row += _format_register_line(f"x{j}", hex_val, decimal, ascii_v, highlight)
            row += "    "
        lines.append(row)

    # Special registers
    lines.append("")
    lines.append(f"  {'fp':<6}  0x{snap.fp:016x}  # {snap.fp}u")
    lines.append(f"  {'lr':<6}  0x{snap.lr:016x}  # {snap.lr}u")
    lines.append(f"  {'sp':<6}  0x{snap.sp:016x}  # {snap.sp}u")
    lines.append(f"  {'pc':<6}  0x{snap.pc:016x}  # {snap.pc}u")
    lines.append(f"  {'cpsr':<6}  0x{snap.cpsr:08x}")

    return "\n".join(lines)


def render_stop_banner(snap: ContextSnapshot) -> str:
    """Render the top banner showing binary, stop reason, and iteration."""
    stripped_tag = f"{Color.RED}[stripped]{Color.RESET} " if snap.is_stripped else ""
    iter_tag = f"  iteration {snap.iteration}" if snap.iteration is not None else ""
    return (
        f"{Color.BOLD}── MACE{Color.RESET}  "
        f"{stripped_tag}"
        f"{Color.GREEN}{snap.binary_name}{Color.RESET}  "
        f"{Color.GREY}{snap.stop_reason}{iter_tag}{Color.RESET}"
    )


def render_match_status(snap: ContextSnapshot,
                        a: int, b: int) -> str:
    """
    Render match/mismatch status for a comparison pair (e.g. w8 vs w9).
    a, b: xN register indices.
    """
    va = snap.w(a)
    vb = snap.w(b)
    match = va == vb
    status = f"{Color.GREEN}MATCH{Color.RESET}" if match else f"{Color.RED}MISMATCH{Color.RESET}"
    delta  = "" if match else f"  delta=0x{abs(va - vb):08x}"
    return f"  w{a} vs w{b}  →  {status}{delta}"


def render_panel(snap: ContextSnapshot,
                 watch: Optional[list[int]] = None,
                 compare: Optional[tuple[int, int]] = None) -> str:
    """
    Full context panel. Entry point for the LLDB stop hook.

    watch:   register indices to highlight
    compare: (a, b) pair to show match/mismatch status
    """
    parts = [
        render_stop_banner(snap),
        render_registers(snap, watch=watch),
    ]
    if compare:
        parts.append(_separator("comparison"))
        parts.append(render_match_status(snap, *compare))
    parts.append(Color.CYAN + "─" * 64 + Color.RESET)
    return "\n".join(parts)
