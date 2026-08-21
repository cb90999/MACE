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

### Stage 2 — reply block success forced
- Function: closure #2 @Sendable (Bool, Error?) in authenticate()
- Offset: 0x5788 from dylib base
- Address: load_addr + 0x5788
- Patch: reg write x0 1
- Effect: success=true → "Access Granted - Secret Content Unlocked"

## Result
Before MACE: "Authentication Failed - No passcode configured"
After MACE:  "Access Granted - Secret Content Unlocked"

## MACE Commands
TODO: paste your actual lldb/MACE command sequence here

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

To be validated against the unstripped build first, confirming this lands
at the same Stage 1/Stage 2 logic already proven manually.
