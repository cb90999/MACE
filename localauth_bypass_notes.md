## Target
- App: MACELocalAuthTest (unstripped, debug build)
- Bundle: com.chidabangalore.MACELocalAuthTest
- Device: palera1n iPad 7th Gen (no passcode configured)

## Vulnerability
LAContext .deviceOwnerAuthentication bypass via two-stage register patch

## Two-Stage Bypass

### Stage 1 — canEvaluatePolicy() forced YES
- Function: static LocalAuthChecker.authenticate()
- Offset: +320 (tbz w0, #0x0)
- Address: 0x100988f2c + 0x140 = 0x10098906c
- Patch: reg write x0 1
- Effect: canEvaluatePolicy returns YES → evaluatePolicy called

### Stage 2 — success boolean check (CORRECTED)
Original notes recorded Stage 2 at dylib offset 0x5788 (closure #2, the outer
reply-block entry point). Re-validated via symbol-free technique on
2026-08-21 and found the actual success-boolean comparison lives one level
deeper.

- Function: closure #1 @Swift.MainActor () -> () in closure #2 @Sendable
  (Swift.Bool, Swift.Optional<Swift.Error>) -> () in
  static LocalAuthChecker.authenticate() -> ()
- Source: LocalAuthChecker.swift:21 (if success == true)
- Dylib-relative offset: 0x59b4 (closure entry) / +48 bytes into closure body
  for the actual comparison instructions
- Instructions patched:
    and    w8, w0, #0x1      ; w8 = success & 1
    and    w9, w9, #0x1      ; w9 = true-literal & 1
    subs   w8, w8, w9        ; compare
    b.ne   <fail path>       ; branch if not equal
- Patch: reg write w0 1 (before the 'and' executes)
- Effect: comparison always evaluates equal -> falls through to
  "Access Granted - Secret Content Unlocked"

## Result
Before MACE: "Authentication Failed - No passcode configured"
After MACE:  "Access Granted - Secret Content Unlocked"

## Symbol-Free Bypass Technique (validated, ASLR-independent)

Proven end-to-end on 2026-08-21 across two separate process launches with
different ASLR slides. Technique requires zero hardcoded addresses and zero
Swift symbol names -- only ObjC selector names, which survive stripping.

### Stage 1 (canEvaluatePolicy guard)

  br set -n "canEvaluatePolicy:error:"
  c                              # hits inside LocalAuthentication framework
  finish                         # returns to caller (own code) via return address
  disassemble -c 20 -s <PC>      # walk forward ~13 instructions to find tbz
  br set -a <tbz address>
  c
  reg write x0 1                 # force guard to pass
  c

### Stage 2 (success boolean check)

  image lookup -r -n "closure #1.*closure #2.*authenticate"
  # resolves the inner MainActor closure containing the real comparison,
  # NOT the outer reply-block closure (which just dispatches to main queue)
  breakpoint set -r "closure #1.*closure #2.*authenticate"
  # sets 2 locations: partial apply forwarder + actual closure body
  # disable the forwarder location, keep the closure body location
  c
  reg write w0 1                 # force success == true
  c

Result: "Access Granted - Secret Content Unlocked"

### Why this matters for Stripped target

canEvaluatePolicy:error: and evaluatePolicy:localizedReason:reply: are ObjC
selectors resolved by the LocalAuthentication framework at runtime -- they
survive Swift symbol stripping entirely, since ObjC dynamic dispatch requires
the selector string regardless of what stripped the caller's own symbols.

The image lookup -r / breakpoint set -r regex approach depends on Swift
closure names being present in the symbol table, which do NOT survive
STRIP_SWIFT_SYMBOLS. On the stripped build, Stage 2 will require either:
(a) manual disassembly from the Stage 1 return address forward, hunting for
    the equivalent branch-on-boolean pattern by inspection, or
(b) binary diffing against the unstripped build's relative offsets, if the
    Release/-O compiler optimization didn't restructure the closure.

## Build Verification

Independently verified at the Mach-O level (not just trusting Cursor's build report):

| Requirement | Verification method | Result |
|---|---|---|
| iOS 15.0 min deployment | `otool -l` LC_BUILD_VERSION | minos 15.0 confirmed |
| LocalAuthChecker.authenticate() static func | `nm -arch arm64 -a` + swift-demangle | Symbol present, offset 0x2194 (simulator dylib) |
| .deviceOwnerAuthentication policy | Functional bypass on no-passcode iPad | Confirmed via working demo |
| Reason string "Prove your identity" | `strings` on debug dylib | Present verbatim |
| Three-way alert branching | Working demo output | All three paths confirmed |
| Unstripped: full symbols, no strip | `nm`/`strings` on debug dylib | Full symbol table present |
| Stripped: symbols/dSYM stripped | `nm` on stripped binary | Empty symbol table, no .dSYM found |
| Stripped: ObjC selectors survive | `strings` on stripped binary | canEvaluatePolicy:error: and evaluatePolicy:localizedReason:reply: both present |

### Key finding — Debug dylib trampoline

Debug/simulator builds (Xcode 16+) use a debug dylib acceleration mechanism.
The main executable is a thin loader that dlopens the real app code from a
companion .dylib at runtime. Swift symbols and type metadata live in:

  MACELocalAuthTest.app/MACELocalAuthTest.debug.dylib

NOT in the main MACELocalAuthTest binary itself. Release/Stripped builds do
not use this mechanism — their code lives directly in the main executable.

### Stripped target — bypass strategy

Symbol-based breakpoints (b LocalAuthChecker.authenticate) will not work on
MACELocalAuthTestStripped since Swift symbols are stripped. However, ObjC
selector strings for the underlying LAContext calls survive stripping:

  canEvaluatePolicy:error:
  evaluatePolicy:localizedReason:reply:

Planned approach: break directly on these selectors via LLDB's ObjC runtime
resolution rather than deriving addresses from a stripped/symbol-free
disassembly:

  br set -n "canEvaluatePolicy:error:"
  br set -n "evaluatePolicy:localizedReason:reply:"

Validated against the unstripped build — confirmed this lands at the same
Stage 1/Stage 2 logic (see "Symbol-Free Bypass Technique" section above).

## Known MACE Bugs Found During This Session

1. stop_hook.py handle_stop() always returns False, which tells LLDB's
   SBStopHook API to auto-continue after rendering the panel. This makes
   mace_on unusable for interactive patch-and-continue workflows (like this
   bypass) since the process never stays stopped for register writes.
   Fix: change return False -> return True in handle_stop().

2. mace_swift_load uses subprocess.run() to invoke swift-section locally on
   the host machine, but accepts device-side paths (e.g.
   /private/var/containers/...) which don't exist on the host filesystem.
   Fails silently with "[MACE] Failed to load Swift context from <path>".
   Fix: either require the user to scp the binary locally first and document
   this, or have MACE auto-pull the binary from the remote target via
   SBTarget/SBModule APIs before invoking swift-section.

Both bugs need fixing before a clean end-to-end MACE-native walkthrough of
this bypass can be recorded (planned as next session).

## MACE-Native Validation Run (2026-08-22)

Full Stage 1 → Stage 2 bypass re-run through mace_on with both bugs fixed.
First fully MACE-native execution of this bypass — panel firing at every
stop, process staying stopped for interactive patching, Swift context
annotated throughout. Confirms the two bug fixes and validates a new
panel feature added in the same session.

### Bugs confirmed fixed on real hardware

1. stop_hook.py auto-continue (handle_stop returning False) — FIXED.
   Process now stays stopped after every panel render. Verified via
   `process status` showing "stopped" immediately after breakpoint hits,
   across multiple iterations in the same session.

2. swift_context.py silent failure on device-only paths — PARTIALLY FIXED.
   Error messages are now specific and actionable (swift-section exit
   code / stderr, or a clear "does not exist locally" message) instead
   of a bare "Failed to load". The attempted auto-resolution via LLDB's
   module cache (SBModule.GetFileSpec()) did NOT work in practice —
   GetFileSpec() returns the same remote path, not a locally cached
   copy, for app-owned dylibs pulled over a debugserver connection.
   Practical workaround used instead: point mace_swift_load at the
   local Xcode DerivedData build artifact (same binary, different
   copy) rather than the device path. This works because Swift type
   metadata is static data compiled into the binary — it does not
   depend on load address or which physical copy is read.
   See BACKLOG.md for the follow-up on a real fix.

### New feature added and validated this session

Swift "you are here" annotation (context_snapshot.swift_location +
lldb_session._annotate_swift_location + context_panel swift section).

Previously, MACE's Swift annotation only fired when stopped at an
objc_msgSend-style call site (receiver in x0, selector in x1). Mid-
function stops via `finish`/`step` — e.g. landing back inside
authenticate() after canEvaluatePolicy returns — showed no Swift
context at all, even with mace_swift_load already run.

Fix: new independent annotation pass using frame.GetFunctionName()
against the loaded SwiftContext, populated on every stop regardless
of whether it's a message-send site. Confirmed working:

  ── swift ──────────────────────────────────────
    [MACELocalAuthTest.LocalAuthChecker.authenticate]

Rendered correctly at both the post-canEvaluatePolicy `finish` stop
and the Stage 1 tbz breakpoint, across a fresh process launch with a
different ASLR slide than prior sessions.

### Full sequence, MACE-native

  mace_swift_load <local DerivedData path to .debug.dylib>
  mace_on
  br set -n "canEvaluatePolicy:error:"
  c                                    # breakpoint 1, panel fires, objc section shown
  c                                    # breakpoint 2 (tbz), panel fires, swift section shown
  reg write x0 1
  c                                    # falls through to evaluatePolicy naturally
  breakpoint set -r "closure #1.*closure #2.*authenticate"
                                       # 2 locations: forwarder (skip) + real closure
  # (dismiss alert, retap Authenticate to trigger fresh cycle)
  c  →  c  →  reg write x0 1  →  c    # Stage 1 again
  c                                    # breakpoint 3.1, forwarder — skip
  c                                    # breakpoint 3.2, real success check, panel fires
  reg write w0 1
  c

Result: "Access Granted - Secret Content Unlocked"

Note: w0 used at Stage 2 to match the 32-bit instruction width shown
in disassembly (and w0, #0x1 / subs w8, w8, w9), but x0 and w0 are
interchangeable here for writing the value 1 — setting the full
64-bit x0 necessarily sets its w0 lower half identically. Only
matters when the upper 32 bits carry meaning or the instruction reads
the full 64-bit register, which is not the case at either patch point
in this bypass.

## mace_patch Validation Run (2026-08-23)

Full Stage 1 -> Stage 2 bypass re-run using the new mace_patch command
(SBValue-based register write via LLDB's Python API) in place of raw
`reg write`, plus mace_patch_history to review the resulting audit
trail. First real validation of mace_patch on live hardware.

### Command

  mace_patch <register> <value>

Examples used this run: `mace_patch x0 1` (Stage 1, tbz guard) and
`mace_patch w0 1` (Stage 2, success boolean).

### What it does differently from raw `reg write`

- Guards against patching a process that isn't stopped (prints a
  clear MACE-branded message instead of LLDB's bare
  "error: Process is running") -- addresses a mistake made repeatedly
  in earlier sessions when a register write was attempted immediately
  after `c` before actually confirming the process had stopped again.
- Writes via frame.FindRegister() -> SBValue.SetValueFromCString(),
  not the `register write` command text -- the API-level approach
  specified in ROADMAP.md rather than shelling out to a command string.
- Reads the register back after writing to confirm the value actually
  took, rather than trusting the write call's success flag alone.
- Records every successful patch to an in-session audit trail
  (register, old value, new value, PC, breakpoint ID, containing
  function, wall-clock timestamp), reviewable at any point via
  mace_patch_history.

### Live output, this run

  (lldb) mace_patch x0 1
  [MACE] x0: 0x0 -> 0x1  at 0x100af906c in static MACELocalAuthTest.LocalAuthChecker.authenticate() -> () (breakpoint 2.1)

  (lldb) mace_patch w0 1
  [MACE] w0: 0x0 -> 0x1  at 0x100af99e4 in closure #1 @Swift.MainActor () -> () in closure #2 @Sendable (Swift.Bool, Swift.Optional<Swift.Error>) -> () in static MACELocalAuthTest.LocalAuthChecker.authenticate() -> () (breakpoint 3.2)

Result: "Access Granted - Secret Content Unlocked" (same as every
prior validation of this bypass).

### mace_patch_history output, this run

  ── MACE patch history ──
    [1]  12:44:22  x0: 0x0 -> 0x1  at 0x100af906c in static MACELocalAuthTest.LocalAuthChecker.authenticate() -> ()  breakpoint 2.1
    [2]  12:47:27  x0: 0x0 -> 0x1  at 0x100af906c in static MACELocalAuthTest.LocalAuthChecker.authenticate() -> ()  breakpoint 2.1
    [3]  12:48:26  w0: 0x0 -> 0x1  at 0x100af99e4 in closure #1 @Swift.MainActor () -> () in closure #2 @Sendable (Swift.Bool, Swift.Optional<Swift.Error>) -> () in static MACELocalAuthTest.LocalAuthChecker.authenticate() -> ()  breakpoint 3.2

Entry [1] is a first Stage 1 patch attempt from earlier in the same
session (before an alert reset the app state and the sequence was
re-run cleanly); entries [2]-[3] are the successful run documented
above. Kept as-is rather than cleared, to show the audit trail
behaves correctly across a realistic multi-attempt session rather
than only a single clean pass.

### Status

mace_patch and mace_patch_history validated end-to-end on real
hardware: process-state guard confirmed (declines to patch a running
process), SBValue-based write confirmed correct via before/after
readback, and audit trail confirmed accurate across multiple patches
in one session. ROADMAP.md v1 feature list updated accordingly.

DVIA v2 itself was not required for this validation, since mace_patch
is target-agnostic -- LocalAuthTest was sufficient to prove the
mechanism. Remaining DVIA v2 / iGoat / InsecureBankv2 work is now
scoped to the features that DO require those specific targets:
passive objc_msgSend annotation against real Objective-C content
(not just Swift-wrapped framework calls), syscall annotation, and
hardware breakpoint mode.
