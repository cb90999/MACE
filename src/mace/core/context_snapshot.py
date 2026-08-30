"""
MACE — Mobile AArch64 Context Extension
core/context_snapshot.py

Captures and holds the full AArch64 register state at an LLDB stop.
This is the central data structure everything else in MACE reads from.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContextSnapshot:
    """
    Immutable snapshot of AArch64 register state at a single LLDB stop.

    Populated by the LLDB session layer; consumed by the display and AI layers.
    All register values stored as Python ints (unsigned 64-bit).
    """

    # --- General purpose registers (64-bit) ---
    x: list[int] = field(default_factory=lambda: [0] * 29)  # x0–x28

    # --- Special purpose registers ---
    fp: int = 0       # x29 — frame pointer
    lr: int = 0       # x30 — link register (return address)
    sp: int = 0       # stack pointer
    pc: int = 0       # program counter

    # --- Status register ---
    cpsr: int = 0     # Current Program Status Register

    # --- Stop metadata ---
    stop_reason: str = ""          # e.g. "breakpoint", "step", "watchpoint"
    breakpoint_id: str = ""        # e.g. "2.1" — populated when stop_reason is "breakpoint"
    binary_name: str = ""          # e.g. "ctf_eea" (stripped) or "MyApp"
    is_stripped: bool = False      # no symbols available
    iteration: Optional[int] = None  # loop counter if detected

    # --- ASLR slide ---
    aslr_slide: int = 0            # load address - file address of main module

    # --- ObjC passive annotation ---
    objc_receiver: str = ""        # x0 class name if stopped at/after objc_msgSend
    objc_selector: str = ""        # x1 selector string if stopped at/after objc_msgSend

    # --- Swift "you are here" annotation ---
    swift_location: str = ""       # e.g. "MACELocalAuthTest.LocalAuthChecker.authenticate()"
                                    # populated whenever Swift context is loaded and the
                                    # current frame resolves, independent of objc_msgSend

    # --- Syscall passive annotation ---
    syscall_name: str = ""         # e.g. "ptrace", "syscall #113" if unrecognized, "" if not
                                    # stopped at a real svc #0x80 instruction
    syscall_number: Optional[int] = None  # signed x16 value at the trap (BSD > 0, Mach trap < 0)
    syscall_kind: str = ""         # "BSD" or "Mach trap" — which XNU convention applies

    # --- Derived helpers ---

    def w(self, n: int) -> int:
        """Return 32-bit view of xN (lower 32 bits), matching AArch64 wN semantics."""
        if n < 29:
            return self.x[n] & 0xFFFFFFFF
        raise ValueError(f"w{n} out of range — use fp/lr/sp/pc directly")

    def as_hex(self, n: int) -> str:
        """Return xN as zero-padded 16-char hex string."""
        return f"0x{self.x[n]:016x}"

    def as_decimal(self, n: int) -> int:
        """Return xN as unsigned decimal."""
        return self.x[n]

    def as_ascii(self, n: int) -> Optional[str]:
        """
        Return printable ASCII interpretation of xN if all bytes are printable.
        Useful for spotting flag characters in registers — core EEA use case.
        """
        raw = self.x[n].to_bytes(8, byteorder='little')
        printable = all(0x20 <= b < 0x7F or b == 0 for b in raw)
        if printable:
            return raw.rstrip(b'\x00').decode('ascii', errors='replace')
        return None

    def w_as_hex(self, n: int) -> str:
        """Return wN (32-bit) as zero-padded 8-char hex string."""
        return f"0x{self.w(n):08x}"

    def file_offset(self) -> int:
        """Return PC as file offset (slide removed) for stable cross-run addresses."""
        return self.pc - self.aslr_slide

    def __repr__(self) -> str:
        return (
            f"ContextSnapshot(pc=0x{self.pc:016x}, "
            f"slide=0x{self.aslr_slide:016x}, "
            f"file_offset=0x{self.file_offset():016x}, "
            f"stop='{self.stop_reason}', "
            f"stripped={self.is_stripped})"
        )
