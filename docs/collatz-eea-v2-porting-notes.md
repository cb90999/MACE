# Collatz+EEA v2 — iOS/Android Porting Notes

Source: targets/src/collatz_eea_v2.s + targets/src/collatz_eea_v2_helpers.c
Purpose: MACE v2.5 "Hardened dual-platform validation" (see ROADMAP.md's
2026-09-14 and 2026-10-03 entries)

## What this is
A deliberately stripped, obfuscated, syscalls-only ARM64 binary combining
Collatz conjecture iteration, the Extended Euclidean Algorithm, and
modular inverse into a dual-accumulator check. Built and validated on
macOS (Apple Silicon). Needs porting to iOS and Android as native targets
so MACE can validate its syscall-annotation feature on a binary where
ALL interesting behavior routes through syscalls -- no libc wrapper
calls (puts, etc.) visible to attach to by name, unlike every other
target used in v1/v2 so far.

**Deliberately preserve as-is: do not fix the collision weakness.**
The dual-accumulator design is NOT actually collision-resistant (see
ROADMAP.md's 2026-10-03 entry for the full analysis -- both
accumulators are effectively byte-wide, and XOR's linearity means many
other inputs pass). This is being kept intentionally, not patched, as
a demo point about what collision-resistant check design looks like
under real shipping deadline pressure. Do not "improve" this during
porting.

## Current (macOS) implementation summary
- ARM64 assembly (`_main`), Mach-O sections (`__TEXT,__text` /
  `__TEXT,__cstring`)
- All interesting values (PRIME, both magic accumulator targets,
  success/failure strings) are hidden behind an `svc` instruction
  trick: `svc #0x10` through `#0x15` deliberately trigger SIGSYS
  (invalid syscall), caught by a `sigaction`-installed handler that
  dispatches to a lookup table of real C functions and writes the
  return value into `x0` of the interrupted context.
- A `constructor`-attribute function does a real `connect()` to
  127.0.0.1:27042 (Frida's default port) before `main` runs; if it
  succeeds, a flag is set that silently corrupts both accumulators
  each iteration -- the binary still "runs" under Frida but always
  denies, with no visible reason why.
- Several opaque predicates (`n*(n+1)` always even, `x XOR x` always
  0, `x*0` always 0) guard fake/dead code paths designed to mislead
  static/LLM analysis toward wrong register values -- confirmed in
  practice to work: an LLM-assisted static analysis attempt gave up
  after 3+ hours, caught by exactly these decoys.

## Porting to iOS — should be close to a straight recompile
iOS and macOS are both Darwin/XNU. Expect these to be unchanged:
- `ucontext_t` layout: `uc_mcontext->__ss.__pc` and `__ss.__x[0]`
  should be identical to macOS's layout on iOS (same XNU `mcontext64`
  struct) -- confirm, don't just assume.
- SIGSYS delivery via an invalid `svc` immediate should behave the
  same under iOS's XNU kernel.
- Mach-O section/symbol conventions (`_main`, `__TEXT,__text`) are
  unchanged -- this is still Mach-O.

What actually changes:
- Code signing — needs a valid provisioning profile/entitlements to
  run on-device, unlike macOS's simpler signing.
- The socket-based Frida check may behave differently under iOS App
  Sandbox / network entitlements. Test this explicitly: a sandboxed
  app failing to open a raw socket at all (a different error path
  than "connection refused") is not the same failure mode the
  original macOS design expects, and could change behavior in a way
  worth knowing about before relying on it for the demo.

## Porting to Android — real porting work, not a recompile
Android is Linux/ELF, a genuinely different platform family from
Darwin. Specific changes needed:
- `ucontext_t` layout is different: Linux aarch64 uses
  `uc_mcontext.pc` and `uc_mcontext.regs[0]` (a flat `mcontext_t`
  with a `regs[31]` array), not `uc_mcontext->__ss.__pc` /
  `__ss.__x[0]`. `svc_handler()` in collatz_eea_v2_helpers.c needs a
  `#ifdef __APPLE__` / `#else` branch (or a separate
  Android-specific source file) with the Linux-correct field
  accesses.
- Mach-O section directives (`.section __TEXT,__text`) have no
  meaning under Android's ELF/GAS assembler -- use plain `.text` /
  `.data`, and drop the Mach-O leading underscore convention (Android/
  Linux uses `main`, not `_main`, for a standalone executable; or
  expose a differently-named native function if called via JNI).
- **Android should be native code, not a Kotlin/Java reimplementation**
  (explicit preference) — build this as a native shared library
  (.so) invoked via JNI from a minimal Activity, keeping the actual
  assembly/C verification logic as the thing MACE attaches to and
  observes. This matches real adversarial-target conditions (a native
  library doing the real work, called from a thin Java/Kotlin shell)
  rather than simplifying the logic away into Kotlin.
- SIGSYS via an invalid `svc` immediate should still work on Android
  (Linux supports SIGSYS for bad/filtered syscalls), but verify it
  isn't intercepted by seccomp-bpf filtering, which some Android
  versions apply more aggressively than stock Linux — test on the
  actual Pixel 10a / Android 16 target, don't assume parity with the
  macOS behavior.
- The Frida-detection `connect()` to 127.0.0.1:27042 should work
  unchanged (same BSD sockets API), but confirm the `INTERNET`
  permission is declared in the manifest, or `socket()` itself may
  fail differently than the "connection refused" the current code
  expects.

## What MACE needs to validate once this exists on both platforms
Per ROADMAP.md's v2.5 framing (syscall-annotation stress test on a
hardened, obfuscated, syscalls-only target):
1. MACE can observe and correctly annotate the custom `svc #0x10`-
   `#0x15` dispatch — not a standard BSD/Mach or Linux syscall number
   range, a genuinely custom table. Good stress test for whether
   MACE's annotation logic over-assumes "the syscall table" is a
   fixed, known set.
2. Register state at each `svc` call site (x20, x24, x26, x28) reads
   correctly via the MACE context panel on both platforms.
3. The Frida-detection corruption path (x28) reads 0 when MACE itself
   is attached via lldb (not Frida) on both platforms — confirming
   MACE's own dynamic instrumentation doesn't trip Frida-style
   detection the way process-injection tools do.
4. (secondary demo goal, not a MACE engineering requirement) Walking
   through the dual-accumulator collision weakness live via MACE —
   showing register values confirm the algorithm, then showing a
   second, different input also passes — doubles as a real-world
   lesson about collision-resistant check design under deadline
   pressure, alongside the primary syscall-annotation validation.
