# MACE — Mobile AArch64 Context Extension

MACE provides an intelligent context panel on every LLDB stop — registers,
disassembly, stack frames, and syscall annotation optimized for mobile AArch64.

On demand, MACE's AI layer interprets the current execution state in plain
language using a local/cloud hybrid routing model that minimizes token burn.

Unlike GEF and pwndbg, MACE uses native LLDB kernel primitives rather than
dynamic library injection, making it transparent to Frida-specific
anti-instrumentation defenses on iOS and Android.

## Status
v0 — in development

## Target
macOS AArch64 (M-series) — LLDB + Python API
