## Purpose

A running record of feedback from people using or reviewing MACE who
aren't its own builder — kept separate from ROADMAP.md (sequencing)
and BACKLOG.md (engineering debt found while building) because
product feedback is a different thing worth its own durable record.
MACE is being built for the broader mobile appsec community, not
just personal use — external reactions matter and shouldn't get lost
in engineering-only documents or a chat history nobody re-reads.

Captured retroactively where needed: the first review below (2026-08-23)
only ever existed as a chat conversation before this file existed — the
resulting engineering work (README rewrite, docs/target-independence.md)
is well documented elsewhere, but the actual feedback that prompted it
had no durable home of its own until now. Worth checking ROADMAP.md/
BACKLOG.md periodically for other feedback-shaped content that's
mixed into engineering docs and belongs here instead.

## 2026-08-23 — friend's full repo review

Full, substantive review of the repo as it stood at the time (roughly
v0-scaffolding stage, before the iOS-focused v1 work that followed).
Assessment was notably stronger than an earlier "is MACE viable?"
conversation — moving from "concept plus a successful L1 solve" to
"platform-aware code plus independent validation experiments."

Positive: praised swift_context.py's DerivedData-fallback handling as
"gritty infrastructure work that makes a tool useful outside a demo";
praised the core/display/lldb/ai package separation as expressing
MACE's actual thesis (ContextSnapshot = generic debugger truth,
SwiftContext = mobile-language awareness, LLDBSession = acquisition,
context_panel = presentation) in a way that would let Android/JNI
context sit beside Swift context later without contaminating the
core.

Critical / suggested:
- README was badly out of date relative to the actual state of the
  project — still said v0/macOS-target/AI-layer-as-if-implemented,
  while the roadmap and source tree had already moved well past that.
  Called this "the weakest representation of MACE" — someone landing
  on the repo cold would underestimate it and misread implemented vs.
  planned. Status: addressed — full README rewrite, 2026-08-23
  (commit 569258e).
- Roadmap's anti-debug-bypass framing was stale relative to
  demonstrated work (MACESecurityTest/IOSSecuritySuite bypass).
  Suggested reframing MACE's stance as narrow, LLDB-native anti-debug
  assistance where execution state can be deterministically observed
  and manipulated — not a universal bypass framework. Status:
  addressed — this exact framing is now in ROADMAP.md's Rationale
  section.
- tests/ directory was essentially empty relative to how much real
  validation was actually happening through external targets (EEA,
  UnCrackable, MACESecurityTest, 8ksec, MobileHackingLab). Suggested a
  VALIDATION.md recording target/platform/capability/result. Status:
  not directly built as a dedicated file, but the underlying need has
  been met differently — every real validation session since has been
  documented in its own dated notes file (dvia2_jailbreak_bypass_notes.md,
  igoat_investigation_notes.md, syscall_annotation_notes.md, etc.),
  giving the same evidentiary record in practice.
- swift_context.py's DerivedData mtime-based selection heuristic
  (most-recently-modified match wins) was flagged as a real
  correctness risk, not just a style note — a stale build touched more
  recently could silently produce wrong type annotations. Suggested a
  binary-identity check (UUID/code-directory hash) before trusting it.
  Status: open — logged as a known limitation where the heuristic was
  introduced; not yet given the suggested identity check.
- Suggested keeping a hard line between "next three engineering
  tasks" and "interesting research" as the backlog grows, so the
  project doesn't start feeling larger than it actually is. Status:
  ongoing discipline, not a one-time fix — this is part of why
  research items get triaged (logged, deferred-with-reasoning, or
  ruled out) rather than accumulated indiscriminately.

Closing assessment, worth preserving verbatim in spirit: the biggest
risk to the project was judged to be documentation drift and scope
diffusion, not technical viability. This became the direct motivation
for docs/target-independence.md (2026-08-23, commit b905c77) and the
"validate before committing" discipline that's been applied to
essentially every session since.

## 2026-08-31 — friend review session (register panel, mace_grep, mace_search)

Positive: single-column register layout, ASLR slide/objc annotation
display, mace_grep, and mace_search specifically called out as
well-liked.

Critical / suggested:
- Panel should be more informative, in the spirit of gdb-gef's
  richness, without becoming a replica of it. Status: done —
  signed-reinterpretation display (2026-09-04, commit 267e8b5) and
  memory-region labeling (BACKLOG.md, Context Panel v2 item 3, not
  yet built) both address this directly.
- Offset/pointer arithmetic convenience, gdb-gef style. Considered in
  depth: LLDB's own expression evaluator (`p/x`, `expr`) already
  provides this natively — not a real capability gap. General-purpose
  arithmetic would duplicate LLDB and macOS Calculator both, low
  value. A narrower, MACE-context-aware version (e.g. arithmetic on
  values mace_search already surfaced this session) might be worth a
  small addition later. Deliberately deprioritized below v1/v2/v3
  feature work — revisit after those land, not before.
