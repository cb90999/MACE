# MACE Backlog

Ideas and future research threads. No version commitment.
Everything here is parked, not forgotten.

## AArch64 Analysis
- PAC-aware backtrace handling (iOS A12+, Android Tensor G4)
- PLT/GOT region annotation in context panel
- Inline hook detection — entry point integrity check
- Heap pointer dereference — follow xN into heap memory
- SVC hidden function call detection (fatalsec/renef pattern)
- Obfuscation CTF binary — IOCCC-style compiler obfuscation target

## Platform
- iOS 26 / usbliter8 BootROM exploit target (iPhone 11, A13)
- Android kernel KGDB via USB-Cereal (Pixel 10a)
- vphone-cli iOS emulator integration
- MASTG KeyStore / crypto key material capture

## AI Layer
- colibri/GLM-5.2 evaluation as local inference tier
- Register pattern recognition — flag check, crypto primitive, loop detection
- objc_msgSend selector annotation
- Syscall argument interpretation from register state

## Toolchain
- pyproject.toml — proper pip installable package
- Portable path resolution (replace hardcoded _MACE_SRC)
- MACE session config file (.macerc)
- GitHub repository — public open source release

## Research References
- fatalsec renef — SVC direct syscall, libantifrida.so
- xairy pixel-kgdb — Android kernel debugging, PAC backtrace corruption
- IOCCC 2025 uellenberg — compiler obfuscation techniques
- Garuda Defender APK — anti-debug detection analysis (Thursday)
- 8ksec OAAE — ARM exploitation cert, MACE as study environment

- node-applesign (pancake/NowSecure) as preferred re-signing tool for
  entitlement-sensitive targets — use -M (massage-entitlements) to
  preserve original app entitlements while removing only privileged ones.
  Replace zsign in ios-setup.md when validated.
  Repo: https://github.com/nowsecure/node-applesign

## Context Panel v2 — Human-First Display
Source: External usability feedback (Aug 2026)

Current gap: MACE panel shows same information as LLDB, just better formatted.
GEF shows MORE information than GDB, surfaced automatically.
Target: Panel must be genuinely useful standalone before AI layer lands.

### Priority improvements:

1. Pointer dereferencing
   Resolve pointer values to human-readable content inline
   x0 = 0x302cf3a50 -> "i am groot!" (NSString)
   x27 = 0x104a714e0 -> MACESecurityTest.__DATA.__objc_const
   Implementation: SBProcess.ReadMemory() + string heuristic

2. Changed register highlighting
   Registers modified since last stop -> highlighted color
   Unchanged registers -> dimmed
   Implementation: ContextSnapshot diff between iterations

3. Memory region labeling
   Append [heap], [stack], [binary.__TEXT], [dylib] to pointer values
   x0 = 0x302cf3a50 [heap]
   x26 = 0x104a714e0 [MACESecurityTest.__DATA]
   Implementation: SBProcess.GetMemoryRegionInfo()

4. Inline string detection
   Any valid pointer -> attempt string read -> display if printable
   Max 64 chars, truncated with ellipsis
   Covers NSString, C strings, Swift strings

5. Branch prediction at current pc
   Show likely next instruction path for conditional branches
   cbz/cbnz/b.eq/b.ne etc -> show both paths, highlight taken
   Makes "what happens next" answerable without stepping

### Reference implementations:
- GEF (hugsy/gef) - original inspiration, GDB
- LLEF (foundryzero/llef, 489 stars) - GEF for LLDB, x86/ARM64/Go
  Borrow: configurable rebase_offset for Ghidra/IDA compatibility

### LLEF coexistence note:
LLEF and MACE are competing stop hooks - do NOT run simultaneously.
LLEF = general RE/VR. MACE = mobile AArch64 specialization.
Study LLEF's UI design, do not combine.

### LIEF integration (lief.re):
Binary parsing backend for MACE context enrichment.
pip install lief - works in LLDB Python environment.
Use cases:
- Automatic __text range for caller filter (replaces image dump sections)
- Stub address resolution -> symbol names
- ObjC selrefs parsing -> passive annotation without EvaluateExpression
- Flutter libapp.so ELF parsing for Dart snapshot offsets
New module: mace/core/binary_context.py

### AI layer is the killer differentiator (v3):
Panel improvements make v1 useful standalone.
AI annotation makes MACE a different class of tool entirely:
"You are stopped inside ISS ptrace check, x0=0x1f = PT_DENY_ATTACH,
patch with reg write x8 0 at offset +1320"
That answer cannot come from panel formatting - only from AI reasoning
over deterministic register state. That is MACE's unique position.

## MachOSwiftSection — Swift Type Annotation Solution
Source: github.com/MxIris-Reverse-Engineering/MachOSwiftSection (284 stars)
Discovered: Aug 2026 — solves Swift type annotation gap from MACESecurityTest session

### Problem solved:
object_getClassName() fails on pure Swift types (ISS, SwiftUI).
MACE annotation returns empty for Swift receivers.
MachOSwiftSection provides Swift-native type resolution.

### Install:
    brew install swift-section

### Capabilities relevant to MACE:

1. SwiftDump — type name resolution
   Resolves x0 pointer to Swift type name
   e.g. x0 = 0x104a714e0 -> IOSSecuritySuite.DebuggerChecker
   Swift equivalent of object_getClassName()

2. SwiftInspection MetadataReader
   Demangles Swift types and symbols against Mach-O at runtime
   Resolves mangled names in annotation panel

3. Static field offsets (--emit-field-offsets)
   Struct member layout computed statically
   When MACE stops inside Swift struct:
   offset +0x08 = ret_errorp, offset +0x10 = ret_pathp
   Makes register interpretation dramatically more useful

4. Protocol conformance mapping
   ISS type hierarchy — which types conform to which protocols
   Enriches annotation with protocol context

### CLI usage before MACE session:
    swift-section dump --architecture arm64 /path/to/binary
    swift-section interface --architecture arm64 /path/to/binary

### MACE integration:
New module: mace/core/swift_context.py
Parse swift-section output at session start
Feed type names into annotation layer for Swift receivers
Complement to LIEF (binary structure) + MachOSwiftSection (Swift semantics)

### Note:
Repo has MCP directory — watch for their MCP server implementation.
May provide Swift binary analysis tools directly as MCP tools.
Coordinate with MACE MCP server design to avoid overlap.

### Relationship to other static tools:
    LIEF              -> binary structure (ELF/Mach-O sections, imports)
    MachOSwiftSection -> Swift semantics (types, fields, protocols)
    Hopper            -> quick iOS disassembly, Swift demangling UI
    JEB               -> deep Android native + iOS ARM64 decompilation
    Together: complete static context feeding MACE dynamic observation

## Dart/Flutter AArch64 Specifics (from Apvrille BlackAlps 2023)
- Object pool register tracking — identify and dereference Dart object pool pointer
  (strings/constants not in __cstring, stored in pool accessed via dedicated register)
- Integer tag awareness — Dart small integers have LSB tag, displayed value = actual * 2
  (MACE must strip tag before showing decimal annotation)
- Stack-based argument convention — Dart pushes args to stack not x0-x7
  (MACE argument annotation must read sp offsets for Dart functions)
- Blutter integration provides addresses for breakpoints without exported symbols
  (bridges the Frida gap Apvrille identifies at BlackAlps 2023)

## Dart ARM64 Register Map (from Worawit Wangwarunyoo, HITB 2023)
Source: Blutter author's primary presentation
From dart/runtime/vm/constants_arm64.h

When MACE context panel shows Flutter/Dart target:
- x15 (R15) → Dart VM Stack Pointer (SPREG), NOT general register
- x16 (R16) → TMP scratch
- x17 (R17) → TMP2 scratch  
- x21 (R21) → Dispatch Table Register
- x22 (R22) → NULL_REG (always caches NullObject())
- x24 (R24) → CODE_REG
- x26 (R26) → THR (current Dart Thread)
- x27 (R27) → PP (Object Pool Pointer)
- x28 (R28) → HEAP_BITS
- x4  (R4)  → ARGS_DESC_REG (Arguments Descriptor)
- x5  (R5)  → IC_DATA_REG

Calling convention:
- Arguments passed on Dart stack (R15), NOT in x0-x7
- Named parameters: R4 = Arguments Descriptor array
- Dart stubs: use specific registers per ABI struct in constants_arm64.h

iOS note: Pointer compression NOT enabled (requires entitlement)
- Full 64-bit object pointers on palera1n iPad
- Simplifies Dart object inspection via MACE memory reads

MACE implementation needed:
- Dart mode detection (check if pc in libapp.so range)
- Conditional register annotation switching to Dart names
- Object pool dereference for string/constant lookup via x27

## Context Panel v2 — Human-First Display
Source: External usability feedback (Aug 2026)

Current gap: MACE panel shows same information as LLDB, just better formatted.
GEF shows MORE information than GDB, surfaced automatically.
Target: Panel must be genuinely useful standalone before AI layer lands.

### Priority improvements:

1. Pointer dereferencing
   Resolve pointer values to human-readable content inline
   x0 = 0x302cf3a50 -> "i am groot!" (NSString)
   x27 = 0x104a714e0 -> MACESecurityTest.__DATA.__objc_const
   Implementation: SBProcess.ReadMemory() + string heuristic

2. Changed register highlighting
   Registers modified since last stop -> highlighted color
   Unchanged registers -> dimmed
   Implementation: ContextSnapshot diff between iterations

3. Memory region labeling
   Append [heap], [stack], [binary.__TEXT], [dylib] to pointer values
   x0 = 0x302cf3a50 [heap]
   x26 = 0x104a714e0 [MACESecurityTest.__DATA]
   Implementation: SBProcess.GetMemoryRegionInfo()

4. Inline string detection
   Any valid pointer -> attempt string read -> display if printable
   Max 64 chars, truncated with ellipsis
   Covers NSString, C strings, Swift strings

5. Branch prediction at current pc
   Show likely next instruction path for conditional branches
   cbz/cbnz/b.eq/b.ne etc -> show both paths, highlight taken
   Makes "what happens next" answerable without stepping

### Reference implementations:
- GEF (hugsy/gef) - original inspiration, GDB
- LLEF (foundryzero/llef, 489 stars) - GEF for LLDB, x86/ARM64/Go
  Borrow: configurable rebase_offset for Ghidra/IDA compatibility

### LLEF coexistence note:
LLEF and MACE are competing stop hooks - do NOT run simultaneously.
LLEF = general RE/VR. MACE = mobile AArch64 specialization.
Study LLEF's UI design, do not combine.

### LIEF integration (lief.re):
Binary parsing backend for MACE context enrichment.
pip install lief - works in LLDB Python environment.
Use cases:
- Automatic __text range for caller filter (replaces image dump sections)
- Stub address resolution -> symbol names
- ObjC selrefs parsing -> passive annotation without EvaluateExpression
- Flutter libapp.so ELF parsing for Dart snapshot offsets
New module: mace/core/binary_context.py

### AI layer is the killer differentiator (v3):
Panel improvements make v1 useful standalone.
AI annotation makes MACE a different class of tool entirely:
"You are stopped inside ISS ptrace check, x0=0x1f = PT_DENY_ATTACH,
patch with reg write x8 0 at offset +1320"
That answer cannot come from panel formatting - only from AI reasoning
over deterministic register state. That is MACE's unique position.

## MachOSwiftSection — Swift Type Annotation Solution
Source: github.com/MxIris-Reverse-Engineering/MachOSwiftSection (284 stars)
Discovered: Aug 2026 — solves Swift type annotation gap from MACESecurityTest session

### Problem solved:
object_getClassName() fails on pure Swift types (ISS, SwiftUI).
MACE annotation returns empty for Swift receivers.
MachOSwiftSection provides Swift-native type resolution.

### Install:
    brew install swift-section

### Capabilities relevant to MACE:

1. SwiftDump — type name resolution
   Resolves x0 pointer to Swift type name
   e.g. x0 = 0x104a714e0 -> IOSSecuritySuite.DebuggerChecker
   Swift equivalent of object_getClassName()

2. SwiftInspection MetadataReader
   Demangles Swift types and symbols against Mach-O at runtime
   Resolves mangled names in annotation panel

3. Static field offsets (--emit-field-offsets)
   Struct member layout computed statically
   When MACE stops inside Swift struct:
   offset +0x08 = ret_errorp, offset +0x10 = ret_pathp
   Makes register interpretation dramatically more useful

4. Protocol conformance mapping
   ISS type hierarchy — which types conform to which protocols
   Enriches annotation with protocol context

### CLI usage before MACE session:
    swift-section dump --architecture arm64 /path/to/binary
    swift-section interface --architecture arm64 /path/to/binary

### MACE integration:
New module: mace/core/swift_context.py
Parse swift-section output at session start
Feed type names into annotation layer for Swift receivers
Complement to LIEF (binary structure) + MachOSwiftSection (Swift semantics)

### Note:
Repo has MCP directory — watch for their MCP server implementation.
May provide Swift binary analysis tools directly as MCP tools.
Coordinate with MACE MCP server design to avoid overlap.

### Relationship to other static tools:
    LIEF              -> binary structure (ELF/Mach-O sections, imports)
    MachOSwiftSection -> Swift semantics (types, fields, protocols)
    Hopper            -> quick iOS disassembly, Swift demangling UI
    JEB               -> deep Android native + iOS ARM64 decompilation
    Together: complete static context feeding MACE dynamic observation
