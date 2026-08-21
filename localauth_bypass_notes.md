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
