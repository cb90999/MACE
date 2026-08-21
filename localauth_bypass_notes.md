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
