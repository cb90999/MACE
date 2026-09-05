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

## v1 — iOS (headline target) — CORE CHECKLIST COMPLETE (2026-09-05)
- debugserver workflow on palera1n iPad (iOS 18.7.2, A10, PAC-free)
  (done ✅ — proven across every session this project)
- MASTG iOS UnCrackable Level 1-3 (L1 done ✅; L2/L3 intentionally
  deferred, not a v1 blocker — see Priority 2 section below, "hardened
  targets" was always scoped as a separate, later goal, not part of
  this checklist's own completion bar)
- objc_msgSend interception and annotation (done ✅ — see Priority 1
  section below for full validation history)
- Syscall annotation (svc #0x80 + x16) (done ✅ — see Priority 1
  section below for full validation history)
- Hardware breakpoint mode for hardened targets (done ✅ — mace_hw_break
  built 2026-09-05, validated live against mach_msg2_trap on real
  hardware, first attempt — see BACKLOG.md and syscall_annotation_notes.md
  for the mach_msg2_trap groundwork this reused)
- README "When to Use MACE" section (done ✅ — 2026-09-04, also
  corrected two stale entries found in the same pass)

## v2 — Android

Scope for the December NowSecure demo (2026-09-06 scoping session):
iPad/iOS 18.x and Pixel 10a/Android 16 only — anything iOS 26/27-adjacent
is explicitly out of scope, and PAC/Flutter work on the Android side is
deliberately deferred rather than treated as equally urgent by default.
Same MVP discipline applied to v1: each priority tier should stand on
its own real value, not need every item bundled in to count as done.

### Priority 1 — load-bearing for the demo
Build in this order — each step is the foundation the next one needs,
mirroring how v1 actually got built (debugserver workflow -> one clean
validation target -> a low-risk high-confidence feature port -> a
second target proving generalization, not overfitting).

- lldb-server on Pixel 10a (Android 16, Tensor G4) — the foundation;
  nothing else below works without this connection existing first,
  the same role debugserver/palera1n played for v1. (partially done —
  platform connection confirmed live and clean, first try, 2026-09-06:
  Triple aarch64-unknown-linux-android, OS Version 36, matching
  getprop's independently-confirmed arm64-v8a/API 36. Real workflow
  fix still needed before this counts as fully done: platform mode's
  `process attach` spawns a dynamic, never-forwarded gdbserver child
  port — see BACKLOG.md. Switch to plain gdbserver + --attach=<pid>
  next session, the same shape as debugserver --attach on iOS.)
- One real MASTG Android target (not the whole set) — proves the core
  connection + context-panel loop end to end. The Android equivalent
  of UnCrackable L1 being v1's first real win, not an exhaustive
  validation pass. (Still open — 2026-09-06 attached to netd, a real
  system daemon, instead. Multithreaded stop-hook/panel rendering
  validated cleanly against it — genuinely harder than anything iOS
  presented, 7 threads hitting one address simultaneously, each
  rendered correctly — but a live system daemon is NOT the right
  target for iterative debugging: caused a real ANR and a real crash
  during the session (both recovered cleanly — see
  android_first_connection_notes.md — but real, avoidable cost).
  Confirms rather than changes this item's own original framing:
  use a disposable, purpose-built test target next time — MASTG
  Android crackmes or Frida-Labs practice APKs, both already logged,
  never a live system process again.)
- Syscall annotation (svc #0 + x8) — genuinely low-risk: the pattern-
  recognition logic (_is_syscall_site()-equivalent) is already proven
  on iOS, and real resources are already in hand for the Linux
  syscall table (register/instruction convention independently
  confirmed 2026-09-05 via fatalsec's "Finding hidden function calls
  using SVC instruction" — see BACKLOG.md's fatalsec renef entry for
  the full research note and arm64.syscall.sh / radare2's `/as` as
  concrete sources). Good early, confidence-building win, same role
  objc annotation played early in v1. (Built and unit-tested 2026-09-06
  — real, complete ARM64 table verified against arm64.syscall.sh
  rather than assumed from memory, 7 mock tests including two
  explicitly checking mutual exclusivity against the XNU annotator in
  both directions. Validated against real, live-observed ground truth
  from netd's own register state (x8=73, ppoll, matching a network
  daemon's normal event loop) before the code was even written. NOT
  yet confirmed firing live on real hardware — blocked by the same
  dynamic-port workflow issue above, not by anything wrong with the
  annotation logic itself. First real target for live confirmation
  once the gdbserver/--attach fix lands.)
- A second validation target (libantifrida.so, or a second MASTG app)
  — proves target-independence rather than overfitting to one app,
  the same discipline that made mace_patch trustworthy (validated on
  two unrelated iOS targets, not just one).

### Priority 2 — deliberately deferred, not a Priority 1 blocker
- PAC-aware pointer display — held pending an empirical check, not
  assumed either way. Tensor G4's CPU cores (Cortex-X4, Cortex-A720,
  Cortex-A520) are ARMv9.2-A, and PAC is part of the ARMv9.0-A+
  baseline architecture, so the SILICON almost certainly supports the
  instructions — but whether stock Android 16 on Pixel actually
  compiles/enforces PAC signing in userspace apps the way iOS mandates
  it across nearly all A12+ code is a separate, unconfirmed software-
  policy question (Android's PAC adoption has historically been
  vendor/toolchain-optional, not universally enforced the way Apple's
  is). Better resolved empirically once lldb-server is actually
  talking to the device than assumed from research alone — check this
  directly once Priority 1's foundation is up, then decide whether
  this feature is even meaningfully in play on this specific device/
  OS build before investing further design time in it.
- Flutter/Dart AOT analysis — a genuinely different runtime paradigm
  (Dart's own AOT compiler, its own object model) beyond even ART's
  complexity, with zero existing foundation to build on (no Dart/
  Flutter equivalent of Swift's DerivedData/type-metadata parsing has
  been designed or discussed at all), and not representative of the
  typical Android app being assessed anyway. Much bigger lift for a
  demo that doesn't need it.

### v2 Design References (research log, Sep 2026)

**On-device debugging — considered, deliberately ruled out.**
ad2001/Ajin Deepak's "gdb-inside-device" post (raw GDB+GEF via Termux
on a rooted AVD) makes a real, credible case that on-device debugging
is dramatically faster than remote host<->target debugging. Considered
directly: MACE's architecture doesn't compete on raw connection
speed -- the actual value sits in the layer built on top of the
connection (context panel, annotation logic, mace_patch's audit
trail), not the connection itself. Switching to on-device debugging
would mean new infrastructure for a benefit that isn't the actual
bottleneck MACE solves, and the post's own tooling (raw GDB+GEF) is a
different debugger entirely from MACE's LLDB Python API foundation --
not a drop-in port. Staying with the remote lldb-server model already
planned above. One separate, genuinely useful detail from the same
research thread, unrelated to the architecture question: Vector
(the actively-maintained LSPosed fork, renamed as of its 2.0 release)
added a "hide traces introduced by the dex2oat hook" feature -- real,
current anti-instrumentation-detection engineering worth knowing about
as background, the same way understanding Frida's own detection
surface was useful even though MACE never adopted Frida's mechanism.

**LSPosed / Vector — corrected status.** The github.com/lsposed/lsposed
repo is the original project and is no longer maintained upstream at
all. The active continuation is a fork by JingMatrix, renamed from
"LSPosed" to "Vector" as of a 2.0 release (March 2026) -- current
support now spans Android 8.1 through 17, including Android 16 (the
version on the already-planned Pixel 10a target above), which the
original repo never reached before going dark. Architecturally still
Zygisk-based systemwide injection -- a different mechanism than
MACE's external-debugger philosophy, not something to adopt directly,
but real, current, correctly-attributed tooling worth knowing the
actual name and status of if it comes up again.

**Ken Gannon (Yogehi/MaliciousErection) Android toolkit bundle** —
real, credentialed researcher (same person behind the Djini/TECNO
advisory referenced above), three pinned repos forming a coherent
Android app-security toolkit rather than disconnected finds:
YayPentestMagiskModuleYay (Magisk module bundling Frida + Movecert
cert-pinning bypass), a modified drozer-agent fork (the standard tool
for exported-component/IPC-based Android app testing), and
cve-2024-4406-xiaomi13pro-exploit-files (Pwn2Own Toronto 2023, DEF CON
32 talk materials) -- folder names (getapps-apks) strongly suggest an
app-layer vulnerability in Xiaomi's own pre-installed GetApps store,
not kernel/browser-layer, though this is inferred from naming rather
than confirmed by reading the exploit code directly. All genuinely
relevant once v2 Android work starts; none of it actionable before
then.

**ad2001/Ajin Deepak — frida-tracing and Frida-Labs.** frida-tracing
(ad2001.com/blog/frida-tracing) demonstrates `frida-trace -i
"module!*pattern*"` -- keyword-bruteforce discovery of candidate
functions in one shot, something MACE genuinely cannot do today (every
breakpoint this project has set has been placed one at a time, after
already knowing roughly what to look for from other means). Worth
naming as a real capability gap for v3's eventual orchestration layer,
not just an Android note. The same post's raw `Memory.writeByteArray`
patch (manually-computed opcode, no readback confirmation, no audit
trail) is useful EXTERNAL validation of mace_patch's own design
choices (SBValue-based write, automatic readback, full audit trail) --
a more robust version of the same fundamental idea, not a criticism of
the blog, which is explicitly educational. Frida-Labs
(github.com/DERE-ad2001/Frida-Labs, 1.3k stars) is real, popular,
structured Frida-on-Android teaching curriculum -- best understood as
a future DVIA-v2/iGoat equivalent for Android (real practice APKs with
known solutions) once v2 work needs one. Its final challenge,
"Patching instructions using X86Writer/ARM64Writer," is a second real
precedent (alongside idamcp's patch_assembly, already logged in v3
Design References) for mace_patch's eventual "tier 2" evolution --
real instruction mnemonics, not just raw register values.

**Android Security Exploits YouTube Curriculum**
(github.com/actuator/Android-Security-Exploits-YouTube-Curriculum,
735 stars, active -- 2026-dated talks present) -- broad, 14-category
list; most of it is genuinely out of MACE's scope the same way the
XNU 1-day repo was (kernel exploits, GPU driver attacks, baseband,
hardware/glitching -- different layer entirely, would need
infrastructure MACE was never scoped to have). Four categories are
real, on-target bookmarks for v2 app-layer work specifically: Android
Reverse Engineering & Obfuscation (complements the jadx-breaking post
above), Android Permissions & Privileges, Webviews & JS Interfaces,
and Input Validation & Path Traversal Attacks. Worth keeping the
scoped subset, not the whole list.

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

Related MHL note (2026-09-04, research log): Mobile Hacking Lab also
publishes a free "ARM64 & LLDB Fundamentals for iOS" course (registers,
stack frames, AAPCS64, iOS ARM64 internals). Not a MACE-vs-course
comparison — a course teaches a human the underlying concepts; MACE
surfaces live, accurate state once someone already knows what they're
looking at. The more useful framing: MACE's panel is genuinely the
kind of instrument that could make a course like this land faster for
a student (learn AAPCS64/stack frames by watching MACE's live panel
demonstrate it correctly, instead of parsing raw lldb register dumps
by hand) — worth keeping as a possible positioning angle for the
NowSecure conversation specifically, given MHL's Djini connection
above.

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

**Tool-legibility lesson from the iGoat-Swift session (2026-08-29,
not an external reference -- our own evidence)** -- while using
mace_grep/mace_search live, Claude (acting as the analyst's assistant
this session, the same role a v3 agent will play) made the exact class
of mistake v3 needs to design against, twice, in different ways:

1. Passed a `-i` flag to mace_grep out of habit from real `grep`, even
   though mace_grep's own docstring says it's already always
   case-insensitive -- there was never a flag to add. Not rejected
   with a usage error; silently misparsed instead, corrupting the
   pattern/command split and producing a confusing downstream lldb
   error instead of a clear "no such flag" message.
2. `image lookup -rn <pattern> <module>` returned empty results that
   were genuinely ambiguous between "no matches" and "this module's
   scoped search is silently broken" (confirmed the latter, separately,
   via `image dump symtab` -- see igoat_investigation_notes.md). A
   human noticing something felt off could stop and cross-check, which
   is what happened, slowly. A v3 agent handed that same empty result
   has no reason to doubt it and could state a wrong, security-relevant
   conclusion ("no jailbreak detection found") with total confidence --
   a worse failure than a malformed command, because nothing about a
   clean empty result looks like a failure.

Same underlying lesson as mrexodia's "route number-base conversion
through a dedicated tool, don't trust the LLM's own math" above,
generalized: don't trust an LLM's generic prior about what a tool
*should* do or what an empty result *should* mean -- the tool itself
has to make its actual contract and actual failure modes legible.
Two concrete implications for v3's MCP layer specifically:

- MCP tool schemas should be generated directly from MACE's own
  source (docstrings, argument parsers) rather than maintained as
  separate prose that can silently drift from what the code actually
  does. The -i mistake happened even though the correct answer was
  already sitting in mace_grep's own docstring -- documentation
  existing isn't sufficient if nothing forces a check against it
  before the agent acts.
- Tools must fail loudly and specifically, for the agent's sake as
  much as the human's -- reject an unknown flag with a clear message
  naming the actual contract, and distinguish "confirmed zero matches"
  from "search may not have run correctly against this module" rather
  than returning the same silent empty result for both. Same "fail
  safe, not silently wrong" principle already behind the objc-
  annotation call-site fix and the address-range-heuristic TODO,
  extended explicitly to agent legibility, not just human correctness.

**v3 design philosophy: "guide through verifiable ground truth," not
"guide through trust"** (CB, 2026-08-30) -- MACE/MACE Armory's v3
posture is close to Morpheus guiding Neo: the agent explains and
proposes, the human decides and acts, never the reverse. Worth being
precise about where the analogy is exact and where MACE's actual bar
is higher, since the difference is the whole point:

Morpheus guides through trust -- Neo has no independent way to verify
what he's told, at least early on; the knowledge asymmetry is total.
MACE is built to guide through VERIFIABLE ground truth instead -- the
agent doesn't ask the analyst to trust its explanation, it shows them
exactly what the deterministic hardware state actually says (real
register values, a real breakpoint ID, a real syscall number decoded
honestly or flagged as unrecognized), so the analyst can check it
themselves. This is the actual throughline connecting mace_patch's
audit trail, the objc/syscall annotation "fail safe, never guess"
design, and the idamcp Security Dashboard reference above (explicit
human approve/deny on every consequential action) -- all of it exists
specifically so the human's trust in an agent's suggestion never has
to be blind, unlike Neo's.

Likely to land well with the actual audience (mobile security
researchers, largely the demographic most likely to get the
reference) -- worth keeping as a real framing device for how v3 is
described externally, not just an internal design note.

**jdb-agentic-debugger** (github.com/brunoborges/jdb-agentic-debugger,
2026-09-04 research log) -- the strongest v3 reference found to date,
and a meaningfully different fit than ida-pro-mcp/idamcp above: those
operate at the STATIC ANALYSIS layer; this operates at exactly MACE's
own layer -- an AI agent controlling a LIVE debugger (JDWP/jdb for
Java, not native/LLDB, but the same discipline). The author's own
stated argument for why a live debugger specifically, not
snapshot/log tools, is close to a verbatim, independently-arrived-at
version of MACE's own differentiator: "many bugs require an agent to
pause the program at a precise moment and interrogate it... that's
what a debugger does -- and only a debugger." Real, substantial
project (56 stars, MIT, 52 commits, author writes for Foojay/Substack/
LinkedIn/DEV/Medium -- a credible, established Java ecosystem figure).

Three concrete design patterns worth citing, none already covered by
the references above:
1. Three-tier agent PRIVILEGE separation, not just tool-category
   separation: jdb-session (the only agent that actually touches the
   live process -- launch, breakpoints, stepping), jdb-diagnostics
   (read-only health checks), jdb-analyst (explicitly "read-only, no
   commands executed" -- pure report synthesis from what the other two
   already gathered). Sharper than idamcp's Security Dashboard or
   mrexodia's ext=dbg gating -- those separate tool categories; this
   separates AGENT ROLES by what they're structurally even allowed to
   touch, with the report-writer unable to execute anything at all.
2. File-based reporting for parallel/background agents, with a
   real stated reason: "avoids the problem of background agents whose
   text responses cannot be read back, and prevents duplicate work
   from re-dispatching." Directly relevant if v3 ever needs to run
   multiple parallel assessment sessions (several challenges, several
   targets) rather than one linear session.
3. "Handoff buttons" -- explicit next-step choices presented to the
   human (Debug interactively / Collect diagnostics / Analyze output)
   rather than the agent silently choosing a path. A different flavor
   of human-in-the-loop than approve/deny on one action -- this is the
   human choosing WHICH KIND of engagement comes next.

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
- iGoat (OWASP iOS training — syscall annotation) (ruled out ✅ —
  confirmed 2026-08-30 via full source clone: zero ptrace/sysctl/
  task_get_exception_ports/getppid/fork() anywhere in the entire
  iGoat-Swift source tree, across every challenge, not just Method
  Swizzling. iGoat is the wrong TARGET for syscall content, not just
  the wrong challenge — see syscall_annotation_notes.md. Actual
  syscall-annotation validation achieved via mach_msg2_trap instead;
  see Features section below)
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
- Syscall annotation — svc #0x80 + x16 (done ✅ — built and validated
  live 2026-08-30, see syscall_annotation_notes.md. Same pattern-
  recognition approach as objc_msgSend annotation: _is_syscall_site()
  recognizes a real "svc #0x80" wherever a stop lands on one, no
  placed breakpoint on the syscall itself needed. Correctly handles
  BOTH BSD syscalls and Mach traps via x16's sign (confirmed live:
  libsystem_kernel.dylib's macx_swapon uses a Mach trap, not a BSD
  syscall, at the identical instruction shape) — validated against
  mach_msg2_trap, first real attempt: [trap #47] (Mach trap), x16
  correctly reinterpreted as signed, honestly reported as
  unrecognized rather than guessed. iGoat ruled out entirely as a
  source of real syscall content along the way (see Targets above);
  MASTG UnCrackable L2 confirmed to have real, functional
  ptrace(PT_DENY_ATTACH) anti-debug on iOS 18.7.2 but proved
  unreachable via debugserver-by-path for reasons not yet understood
  — real finding in its own right, logged in full, not needed for
  this feature's validation in the end)
### Priority 2 — Hardened targets once features are proven
Anti-debug bypass is a prerequisite problem, not the MACE headline.
Attempt these after all v1 features are validated on cooperative targets.

Targets:
- MASTG iOS UnCrackable L2 (ptrace loop — needs Liberty Lite or bypass
  tweak) (real anti-debug confirmed 2026-08-30 — ptrace(PT_DENY_ATTACH)
  genuinely functional on iOS 18.7.2 when launched normally, confirmed
  via the documented debugserver-segfault-on-attach signature. Not yet
  attempted via a route that both catches the check AND allows
  continued debugging — see syscall_annotation_notes.md. Independently
  useful: reproducible confirmation of OWASP's own known issue #1634)
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

UPDATE 2026-09-04 (research log, ad2001/Ajin Deepak, "The Tale of
Breaking Android Decompilers"): real, working caveat on this skill's
whole mechanism, not a new item. A 4-byte AXML manifest corruption
defeats jadx (older versions) and apktool while Android's own runtime
AXML parser tolerates it and runs the app normally -- cited as
actually used by SpyNote, a known Android RAT family. Doesn't
invalidate the skill (most real apps aren't deliberately corrupted
this way), but a real, credible failure mode worth knowing before
trusting a jadx-based pipeline against a genuinely hostile or
malware-adjacent target -- the tool can silently fail to decompile
correctly rather than erroring out.

### JEB + MACE MCP Integration (stretch goal, Nov or post-GA)
mace_get_jeb_analysis(pc) → decompiled function context at current stop
Combines static JEB context with live MACE register state in one agent call.
Full static-to-dynamic pipeline in single MCP interface.
