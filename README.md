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
  Caller-filtered to skip system/framework noise. *(In progress —
  validated on Swift-wrapped framework calls; not yet stress-tested
  against a target with substantial native Objective-C content.)*
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

## Planned (not yet implemented)

- **AI-layer plain-language interpretation** — reasoning over
  deterministic register state to answer "what am I looking at and how
  do I proceed" in natural language. This is the intended v3
  differentiator; the panel above is designed to be genuinely useful on
  its own before this layer lands, not a placeholder for it.
- **Syscall annotation** (`svc #0x80` + `x16`)
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
