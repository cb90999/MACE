# MACE — Mobile AArch64 Context Extension

MACE is an LLDB-native context panel and register-patching toolkit for
mobile AArch64 security research — GEF/pwndbg-style situational awareness
for iOS (and eventually Android) debugging, built on LLDB's Python API
rather than dynamic library injection.

## Status
v1 — active development. Core capabilities below are implemented and
validated against real iOS hardware; items under "Planned" are not yet
built. See `ROADMAP.md` for current sequencing and `BACKLOG.md` for
parked research threads.

## What works today

- **Context panel on every LLDB stop** — full AArch64 register state
  (single-column, GEF-style), decoded CPSR condition flags, stack
  pointer/frame pointer/link register/PC, ASLR slide and file-relative
  offset so addresses stay comparable across process relaunches.
- **Swift type annotation** — resolves the current frame to its Swift
  type/method ("you are here: `LocalAuthChecker.authenticate()`"),
  backed by `swift-section` parsing of the target binary's type and
  field-offset metadata. Works whether the debugged binary is local or
  device-only (auto-resolves against Xcode DerivedData when the module
  isn't reachable on the host filesystem).
- **Passive Objective-C annotation** — when execution is stopped inside
  app-owned code that just called into `objc_msgSend`, annotates the
  receiver class and selector without requiring a global breakpoint.
  Caller-filtered to skip system/framework noise. Validated on
  Swift-wrapped framework calls and, since 2026-08-30, on substantial
  native Objective-C content (DVIA-v2's plist write —
  `[__NSDictionaryM writeToFile:atomically:]`, both receiver and
  selector resolved correctly from live register state), confirming
  the call-site detection generalizes beyond the original validation
  target.
- **Passive syscall annotation** — when execution is stopped directly
  at a real `svc #0x80` instruction, decodes the pending BSD syscall or
  Mach trap from `x16`, correctly handling both conventions (positive
  = BSD syscall, negative = Mach trap — the same trap instruction
  serves both on AArch64/XNU). Unrecognized numbers are reported
  honestly (`syscall #113`, `trap #103`) rather than guessed. No
  breakpoint on the syscall itself required — recognizes the pattern
  wherever a stop happens to land on it.
- **`mace_patch`** — register writes via LLDB's `SBValue` API rather
  than shelling out to the `register write` command text. Guards
  against patching a process that isn't stopped, confirms the write by
  reading the register back, and records every patch (register,
  before/after value, PC, breakpoint ID, containing function,
  timestamp) to an in-session audit trail reviewable via
  `mace_patch_history`.
- **Breakpoint identification** — every panel surfaces the exact
  breakpoint ID that fired (e.g. `breakpoint 2.1`), matching LLDB's own
  stop-reason output, rather than an undifferentiated "breakpoint".
- **`mace_grep` / `mace_search`** — filter a broad LLDB command's
  output down to matching lines (`mace_grep <pattern> <command>`), or
  search this session's own stop history by address or annotation
  string (`mace_search <address|string>`). Built specifically for
  large, hard-to-scroll output (module lists, symbol table dumps) and
  for re-finding a specific earlier stop without scrolling back
  through terminal history.

## When to use MACE

MACE fits a specific, narrower role than a general instrumentation
framework — worth being explicit about both sides of that.

**Good fit:**
- Assessing anti-debug, anti-tamper, or jailbreak-detection logic where
  you need real, deterministic register state at a precise moment —
  not a static guess at what a check does, but what it actually did.
- Targets where Frida injection is detected, blocked, or simply
  undesirable — MACE observes and patches through LLDB's own debugger
  protocol, a different vantage point than in-process injection (see
  "Why LLDB-native instead of Frida" below).
- Validating a specific bypass hypothesis with one targeted register
  write, backed by a real audit trail (`mace_patch` — see above),
  rather than a broad, unaudited patch.
- Situations where manually cross-referencing a symbol table or
  disassembly for every stop is the actual bottleneck — the objc/Swift/
  syscall annotation above exists specifically to remove that step.

**Not the right tool:**
- Constructing memory-corruption exploits, sandbox escapes, or kernel
  privilege-escalation chains. This is a different discipline entirely
  from what MACE does — see `ROADMAP.md`'s Rationale section. MACE
  observes and patches an already-cooperative, already-attached
  process; it does not build the access to get there.
- Broad static analysis or decompilation — that's Hopper, JEB, or
  jadx's job. MACE is a live, dynamic tool; pair it with a static
  analysis pass, don't expect it to replace one.
- A quick, one-off hook where injection isn't blocked and determinism
  doesn't matter — Frida is faster and easier for that. MACE's value
  is specifically when Frida can't be used, or when the audit trail
  and register-level precision matter more than convenience.
- Kernel-level or baseband-level analysis — a different layer entirely,
  with different debugging infrastructure MACE was never scoped to
  have.

## Planned (not yet implemented)

- **AI-layer plain-language interpretation** — reasoning over
  deterministic register state to answer "what am I looking at and how
  do I proceed" in natural language. This is the intended v3
  differentiator; the panel above is designed to be genuinely useful on
  its own before this layer lands, not a placeholder for it.
- **Hardware breakpoint mode** for hardened/anti-debug targets
- **Android support** — architecture is designed to accommodate a
  parallel Android/JNI context layer alongside the Swift-specific one,
  but no Android target has been attempted yet.

## Host vs. target

MACE runs on **macOS (Apple Silicon)** as the host, using LLDB's Python
scripting API. The debug **target** is a real iOS device (validated on a
jailbroken iPad, A10, iOS 18.7.2) reached over a `debugserver` connection
— MACE does not require or use a jailbroken host, only a jailbroken (or
otherwise debuggable) target device.

## Why LLDB-native instead of Frida

MACE deliberately avoids dynamic library injection. On iOS 18.7.2,
Frida and a native LLDB `debugserver` attach cannot coexist on the same
process — so for targets where Frida instrumentation is detected,
blocked, or simply undesirable, MACE offers a different vantage point:
observing and patching execution state directly through the debugger,
below the layer most anti-instrumentation checks are built to detect.
This is a narrower, more deterministic capability than a general
bypass framework — see `ROADMAP.md` for what's actually been validated
versus what's aspirational.

## Engineering discipline

MACE targets platform patterns, not test cases — a feature is only
considered generalized once validated against targets that had no
influence on how it was written. See `docs/target-independence.md`
for the full principle and how it's applied in practice.
