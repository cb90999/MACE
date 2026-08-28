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
- objc_msgSend interception and annotation (done ✅ — see Priority 1
  section below for full validation history)
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


### v3 Design References (research log, Aug 2026)

**llmfit** (github.com/AlexsJones/llmfit) — directly actionable for the
DSPy local/cloud routing line above, not just inspiration. Native Apple
Silicon support (system_profiler-based unified memory detection, Metal
backend — matches our actual M4/M5 hardware, unlike FreeToken below).
Machine-readable `recommend --json` and a `serve` REST mode explicitly
built for agent/scheduler consumption; `bench --quality --routing`
outputs a role-based quality-scoring routing matrix. Concrete plan: the
DSPy router queries a local `llmfit serve` instance at decision time to
learn what's actually capable enough to run locally right now, falling
back to a commercial API only when nothing local clears the bar —
rather than hardcoding a static "good enough" model list. Also ships an
OpenClaw agent skill demonstrating the same "agent queries llmfit,
decides routing" pattern for a different agent framework — worth a
look when the DSPy layer gets built.

**FreeToken** (arxiv.org/pdf/2608.16157) — considered and ruled out as
a direct reference. Solves MoE expert-streaming between discrete GPU
VRAM and host RAM over PCIe; that split doesn't exist on Apple Silicon's
unified memory, so the core mechanism doesn't transfer. The broader
thesis (frontier open-weight models increasingly viable to run locally)
is worth remembering if/when local-vs-cloud tradeoffs get revisited,
but llmfit is the actually-applicable tool for our hardware.

**mrexodia/ida-pro-mcp** and **idamcp/idamcp** (fork/independent
evolution of the same lineage) — closest existing reference
implementations to "what MACE's v3 MCP layer wants to be": both expose
a live-debugger tool surface (register read, breakpoints, memory
read/write) via MCP, at a similar granularity to the tool list above.
Concrete patterns worth reusing:
- `ext=dbg`-style opt-in gating for state-mutating tools, separate from
  read-only inspection — same instinct already behind mace_patch's
  stopped-process guard; worth extending to the MCP tool boundary.
- idamcp's Security Dashboard — human explicitly approves/denies
  "unsafe" tool calls in real time. Best existing precedent found for
  how a human analyst stays genuinely in control of an agent doing
  live patching, matching v3's "agent + human analyst" framing (not
  an autonomous agent).
- idamcp's relational SQL layer over synced disassembly state (one
  `sql_query` instead of dozens of sequential tool calls) — relevant
  once MACE has a session's worth of patch_history/breakpoint hits/
  Swift-annotated stops an agent needs to query in aggregate.
- idamcp's Keystone-based `patch_assembly` (write real instruction
  mnemonics with symbol resolution, not just raw register values) —
  a real "tier 2" direction for mace_patch once it outgrows simple
  register writes.
- Independent, real-world confirmation of target-independence: idamcp's
  own writeup describes rewriting x86-specific heuristics to be
  architecture-agnostic (ARM, AArch64, MIPS, PowerPC, RISC-V) — same
  failure mode docs/target-independence.md exists to catch, hit by a
  different team in a directly analogous MCP+RE context.
- mrexodia's "Tips for Enhancing LLM Accuracy" section: never let the
  LLM do number-base conversion itself (dedicated `int_convert` tool —
  LLMs hallucinate on raw hex/decimal math); de-obfuscate/normalize a
  target before reasoning over it. The second point maps directly onto
  MACE's own anti-debug bypass work — mace_patch clearing an ISS/ptrace
  check IS that normalization step, done before an agent reasons over
  the resulting clean state.

**Djini** (djini.ai, Mobile Hacking Lab's AI pentesting tool) — real,
working existence proof that the v3 product shape works in practice,
not just architecture. Their public advisory (TECNO Spark 30 Pro
one-click RCE) shows an AI agent tracing intent-routing taint from an
exported entry point through to a WebView sink, confirming an
authorization-gate bypass, and auto-generating a working PoC — human
steering, agent doing the structured analysis. Worth studying as a UX/
workflow reference for the "agent + human analyst" loop, not as code
(their substrate is Android app-layer static analysis, not live AArch64
register work — genuinely complementary to MACE, not overlapping). Also
worth knowing: Mobile Hacking Lab is the same org behind the
MobileHackingLab validation targets already named in this roadmap —
relevant landscape awareness, not a dependency.

**Byte-level perplexity model for packing/obfuscation triage**
(cocomelonc.github.io, "Malware analysis: part 11", July 2026) — NOT a
local-LLM candidate for the DSPy routing line above; a materially
smaller, different category of thing worth being precise about. A
~600K-parameter decoder-only transformer, trained from scratch in
~25 seconds, that predicts next-byte-given-previous-bytes over raw
machine code and uses its own perplexity (how "surprised" it is) as a
packing/encryption detector — ROC-AUC 0.994 on a synthetic (LZMA-based)
packed-vs-normal benchmark in the source post. Classifier/anomaly-
signal, not a reasoning engine.

Two concrete ties to work already in this roadmap:
- Practical mechanism for the ida-pro-mcp "de-obfuscate before
  reasoning" lesson above — a fast, local, sub-second perplexity score
  on a memory region gives the agent a cheap way to decide WHEN
  normalization is needed before spending reasoning tokens on it,
  rather than guessing.
- Plausible fit for InsecureBankv2's named validation goal ("crypto key
  material in registers", Priority 1 targets above) — a trained
  byte-perplexity model is well suited to distinguishing "this looks
  like a real key/random blob" from "this looks like a normal pointer
  or structured data" in a register/memory dump.

Caveats carried forward honestly from the source post, not glossed
over: the trained weights in the post are useless for MACE as-is
(trained on x86 ELF from /usr/bin; our domain is entirely AArch64
Mach-O) -- would need a from-scratch retrain on a legitimate-ARM64-
binary corpus, which the technique's own appeal (25s CPU training)
makes cheap, not a blocker. Also: synthetic benchmark only (LZMA-
simulated packing, not real-world packers/malware), and the author's
own stated limitation that padding normal-looking bytes can lower a
file's average surprise adversarially -- one signal among several,
not a verdict on its own.

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
- DVIA v2 (Prateek's app — objc annotation, mace_patch) (done ✅ —
  validated 2026-08-27, see dvia2_jailbreak_bypass_notes.md. Second
  unrelated target for mace_patch (target-independence bar now met);
  first real-ObjC-content validation of passive objc_msgSend
  annotation. Also surfaced a new bug in the annotation path — see
  BACKLOG.md "objc annotation fires without confirming real
  objc_msgSend call site")
- iGoat (OWASP iOS training — syscall annotation)
- InsecureBankv2 (crypto key material in registers)

Features to validate on these targets:
- Passive objc_msgSend annotation with caller filtering (done ✅ —
  fully validated 2026-08-28. Real ObjC dispatch confirmed correct
  via DVIA-v2's [NSFileManager defaultManager] call (2026-08-27); the
  misattribution bug found the same day (fired on non-message-send
  stops when a register happened to look pointer-shaped) is now fixed
  — _is_objc_msgsend_call_site() confirms a real bl-to-objc_msgSend at
  pc before trusting x0/x1. Reproduced the exact original bug scenario
  live (jailbreakTest3 prologue, identical x1 value) three times —
  correctly shows no annotation now — then confirmed the real call
  site in the same function still annotates correctly. See
  BACKLOG.md for the fix writeup)
- mace_patch — register modification via SBValue API (done ✅ — validated
  2026-08-23 on MACELocalAuthTest, both Stage 1/Stage 2 bypass patches
  applied via mace_patch with correct before/after values, breakpoint
  IDs, and full audit trail via mace_patch_history; validated again
  2026-08-27 on DVIA-v2 — a second, genuinely unrelated target,
  confirming the mechanism is target-agnostic rather than overfit to
  MACELocalAuthTest)
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

### Android Static — candidate companion tool (research log, Aug 2026)
github.com/SimoneAvogadro/android-reverse-engineering-skill — a Claude
Code skill (jadx/Fernflower decompile → search decompiled source for
Retrofit/OkHttp/Ktor/Apollo/Koin API calls, plus Kotlin metadata-based
R8 deobfuscated name recovery). Not a MACE dependency — entirely static,
no live process, wrong layer for MACE's core (live AArch64 register
work). Two things worth keeping:
- Candidate Android-side static source for the same "static context
  feeds an agent alongside MACE's live observation" MCP pipeline JEB/
  Hopper already fill for iOS — real static triage available today,
  ahead of MACE's own Android/KGDB work (not started, see v2 section).
- Their Kotlin `@Metadata`/`@DebugMetadata` name-recovery technique is
  the same underlying pattern as MACE's Swift annotation work: runtime
  metadata a stripping pass can't remove without breaking the runtime
  itself that depends on it. Independent, cross-platform confirmation
  the pattern is real, not an iOS-specific hack.

### JEB + MACE MCP Integration (stretch goal, Nov or post-GA)
mace_get_jeb_analysis(pc) → decompiled function context at current stop
Combines static JEB context with live MACE register state in one agent call.
Full static-to-dynamic pipeline in single MCP interface.
