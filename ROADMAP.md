# MACE Roadmap

## v0 — macOS Scaffolding (COMPLETE)
- ContextSnapshot dataclass
- GEF-like context panel with ANSI color
- LLDBSession SBFrame bridge
- stop hook — mace_on / mace_off
- trace mode — mace_trace_on / mace_trace_off
- .lldbinit auto-loader
- Validated against EEA binary (debug + stripped)
- 5 target binaries: debug, stripped, obf_debug, obf_stripped, obf_hardened

## v0.1 — macOS Polish
- wN display alongside xN when upper 32 bits are zero
- ASLR slide calculation — automatic base address handling
- Terminal width auto-detection
- pyproject.toml — proper package installation
- Validate trace mode against obfuscated + hardened EEA binary

## v1 — iOS (headline target)
- debugserver workflow on palera1n iPad (iOS 18.7.2, A10, PAC-free)
- MASTG iOS UnCrackable Level 1-3
- objc_msgSend interception and annotation
- Syscall annotation (svc #0x80 + x16)
- Hardware breakpoint mode for hardened targets
- README "When to Use MACE" section

## v2 — Android
- lldb-server on Pixel 10a (Android 16, Tensor G4)
- MASTG Android targets
- Syscall annotation (svc #0 + x8)
- PAC-aware pointer display
- libantifrida.so as validation target
- Flutter/Dart AOT analysis

## v3 — AI + MCP (NowSecure demo target)
- MCP server — mace_get_register_context, mace_set_breakpoint,
  mace_read_memory, mace_get_backtrace, mace_step_instruction
- DSPy routing — local/cloud hybrid
- Telemetry opt-out by default
- SSE server mode for remote debugging
- NowSecure webinar demo — October/November

## objc_msgSend Annotation Design

Problem: global objc_msgSend breakpoint fires thousands of times per second,
freezing the UI and making the app unusable during debugging.

Root cause: objc_msgSend is an extraordinarily high-frequency dispatcher.
Any breakpoint — software or hardware — still stops execution when triggered.
Auto-continue Python callbacks still require stop/callback/resume cycles.
Global tracing is incompatible with a responsive mobile UI.

### v1 Implementation — Passive annotation at existing stops

When MACE is already stopped for another reason, inspect the current
instruction. If it is a call to objc_msgSend, resolve:
- x0 as the receiver class name
- x1 as the selector string
- caller symbol and app-module offset

No global objc_msgSend breakpoint needed. Zero overhead. Fits the
context panel mission exactly.

### Backlog — Narrower tracing approaches

1. Call-site breakpoints — statically locate app-owned bl objc_msgSend
   call sites and break only on those addresses. Avoids UIKit/Foundation noise.

2. Selector-targeted tracing — analyst requests specific selector:
   mace_objc_trace authenticateUser:
   MACE resolves a narrow strategy rather than global dispatch tracing.

3. Offline disassembly annotation — annotate likely ObjC message-send
   sequences from nearby register-loading instructions and selector references.

### Hardware breakpoints — corrected understanding

Hardware breakpoints avoid modifying executable code with a software trap
instruction, but still stop execution when triggered. They help with:
- integrity-sensitive code that scans for BRK opcodes
- breakpoint count limits (ARM64 has 6 hardware breakpoints)
They do NOT solve high-frequency stop overhead.

## v1 Target Sequencing (revised)

### Priority 1 — Feature development on cooperative targets
Build and validate each MACE feature against apps with no anti-debug friction.
Clean debugserver attach, full MACE capability demonstration.

Targets:
- MASTG iOS UnCrackable L1 (done ✅)
- DVIA v2 (Prateek's app — objc annotation, mace_patch)
- iGoat (OWASP iOS training — syscall annotation)
- InsecureBankv2 (crypto key material in registers)

Features to validate on these targets:
- Passive objc_msgSend annotation with caller filtering (in progress)
- mace_patch — register modification via SBValue API (done ✅ — validated
  2026-08-23 on MACELocalAuthTest, both Stage 1/Stage 2 bypass patches
  applied via mace_patch with correct before/after values, breakpoint
  IDs, and full audit trail via mace_patch_history; DVIA v2 itself not
  required for this validation since the mechanism is target-agnostic)
- Syscall annotation (svc #0x80 + x16)
- Hardware breakpoint mode

### Priority 2 — Hardened targets once features are proven
Anti-debug bypass is a prerequisite problem, not the MACE headline.
Attempt these after all v1 features are validated on cooperative targets.

Targets:
- MASTG iOS UnCrackable L2 (ptrace loop — needs Liberty Lite or bypass tweak)
- MASTG iOS UnCrackable L3
- Garuda Defender APK analysis
- Production app assessments

### Rationale
Frida and MACE cannot coexist on iOS 18.7.2 (proven Aug 1 2026).
Anti-debug bypass is infrastructure, not MACE capability.
Demonstrating full MACE features on cooperative targets is more
compelling for NowSecure demo than fighting bypass infrastructure.

## objc_msgSend Annotation — Swift Type Support

Current implementation uses object_getClassName() which works for ObjC receivers.
Pure Swift types (ISS, SwiftUI) return empty or fail silently.

Needed: Swift metadata type resolution
Options:
- frame.EvaluateExpression with Swift type introspection
- SBValue.GetTypeName() on x0 register value  
- swift_getTypeName() runtime function

Validated: caller filter working correctly (lr range check passes for debug dylib)
Gap: type name resolution for Swift receivers

## Static Analysis Tool Integration

### iOS Static → MACE Dynamic Pipeline (Hopper)
Hopper Disassembler — already licensed ($99 lifetime)

Workflow:
1. Load IPA/Mach-O in Hopper
2. Swift symbol demangling automatic
3. Find target function → copy offset
4. MACE: br set -a <load_addr> + <offset>
5. Observe registers at runtime

Hopper strengths for iOS:
- Fast Mach-O loading vs JEB
- Native Swift demangling
- Pseudo-code for ARM64
- Python scripting API (Hopper v5+)
- Lightweight for quick iteration

### Android Static → MACE Dynamic Pipeline (JEB)
JEB Android — monthly trial ($140/month) → annual ($1,200/year) if validated

Workflow:
1. Load APK or native .so in JEB
2. JEB recovers DEX classes + native ARM64 symbols
3. Find target function offset in JEB
4. MACE: br set -a <load_addr> + <offset>
5. Observe registers at runtime

JEB strengths for Android/iOS:
- DEX/Dalvik decompilation (Android Java/Kotlin)
- ARM64 native decompilation (works on iOS Mach-O too)
- Flutter libapp.so symbol recovery
- Unity GameAssembly.so IL2CPP symbols
- Python API (jeb.api) → MCP server integration

Validation checklist (monthly trial):
- Flutter libapp.so → Dart symbol recovery → MACE breakpoints
- Unity GameAssembly.so → IL2CPP symbols → MACE breakpoints
- iOS Mach-O → Swift decompilation quality vs Hopper
- jeb.api Python prototype → MCP tool call feasibility

### JEB + MACE MCP Integration (stretch goal, Nov or post-GA)
mace_get_jeb_analysis(pc) → decompiled function context at current stop
Combines static JEB context with live MACE register state in one agent call.
Full static-to-dynamic pipeline in single MCP interface.

## Static Analysis Tool Integration

### iOS Static → MACE Dynamic Pipeline (Hopper)
Hopper Disassembler — already licensed ($99 lifetime)

Workflow:
1. Load IPA/Mach-O in Hopper
2. Swift symbol demangling automatic
3. Find target function → copy offset
4. MACE: br set -a <load_addr> + <offset>
5. Observe registers at runtime

Hopper strengths for iOS:
- Fast Mach-O loading vs JEB
- Native Swift demangling
- Pseudo-code for ARM64
- Python scripting API (Hopper v5+)
- Lightweight for quick iteration

### Android Static → MACE Dynamic Pipeline (JEB)
JEB Android — monthly trial ($140/month) → annual ($1,200/year) if validated

Workflow:
1. Load APK or native .so in JEB
2. JEB recovers DEX classes + native ARM64 symbols
3. Find target function offset in JEB
4. MACE: br set -a <load_addr> + <offset>
5. Observe registers at runtime

JEB strengths for Android/iOS:
- DEX/Dalvik decompilation (Android Java/Kotlin)
- ARM64 native decompilation (works on iOS Mach-O too)
- Flutter libapp.so symbol recovery
- Unity GameAssembly.so IL2CPP symbols
- Python API (jeb.api) → MCP server integration

Validation checklist (monthly trial):
- Flutter libapp.so → Dart symbol recovery → MACE breakpoints
- Unity GameAssembly.so → IL2CPP symbols → MACE breakpoints
- iOS Mach-O → Swift decompilation quality vs Hopper
- jeb.api Python prototype → MCP tool call feasibility

### JEB + MACE MCP Integration (stretch goal, Nov or post-GA)
mace_get_jeb_analysis(pc) → decompiled function context at current stop
Combines static JEB context with live MACE register state in one agent call.
Full static-to-dynamic pipeline in single MCP interface.
