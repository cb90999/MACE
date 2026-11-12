# MACE — Session Handoff

Last updated: 2026-11-05
Repo branch: main
Validated through: v2.5 (eeacollatz) CLOSED — iOS opaque-predicate bug
found, root-caused, and fixed (the `charset_ok` block was undocumented
noise gated on an always-true Frida-detection flag, not part of the
real accumulation); iOS re-validated with zero MACE patches applied
("Access Granted!"); Android re-validated at the register level
(`x0 == x26` at `check_flag`'s real comparison, unpatched) before two
unrelated interruptions (an lldb/adb disconnect and a pre-existing
ART-level SIGSEGV, confirmed via logcat tombstone comparison to
identical crashes predating this week's changes) cut the session
short. Decision made NOT to chase a clean Android screenshot by
re-running eeacollatz again — N4TIVE ch03/ch04 (already solved
end-to-end on the Pixel 10a) stand as Android's half of the
cross-platform demo story instead, since re-proving the same fix
twice demonstrates less than two distinct bug classes per platform.
v3 demo lineup finalized: iOS = eeacollatz, Android = N4TIVE
ch03/ch04 + RedRunner (open-source Unity/IL2CPP game, replacing the
internal-only SpinCube test app as the "real game" showcase).
Pre-v3 UI cleanup CLOSED (2026-11-01) — 8 UI/discoverability fixes
plus full memory-region labeling implemented, committed, and
live-verified on eeacollatz/Enigma (iOS); two real findings surfaced
during live verification were root-caused and fixed the same
session.
Current milestone: v3 AI+MCP, findings-JSON ingestion sub-feature
CLOSED (2026-11-02) — implemented, extended with symbol+offset
resolution and a cross-platform module-lookup fix (both found
necessary via live device work, not speculative design), and
live-validated end-to-end on BOTH platforms: iOS (eeacollatz) and
Android (N4TIVE ch04, full real bypass confirmed via the app's own
UI reaching Status: SOLVED). Rest of v3 (AI+MCP architecture) still
fully ahead; JEB MCP integration confirmed out of December-deadline
scope (2026-11-02, see Active milestone below) -- always a stretch
goal, now explicitly closed out rather than left ambiguous.
v3 architecture (four-layer: lldb -> MACE MCP channel -> separate MCP
server process -> Claude Agent SDK orchestrator) designed and recorded
2026-11-03 (ROADMAP.md), including Dec-scope decisions (single agent,
tool-gated permissions; real enforced approval gate; DSPy routing and
RedRunner/N4TIVE-ch03 findings-JSON deferred) and four extension seams
for GA. Implementation started same day: step 1 (lldb-side MCP
channel, src/mace/mcp/channel.py) and step 2's full read-only
diagnostics tool set (mace_get_register_context, mace_read_memory,
mace_get_backtrace) built and live-validated on real iOS hardware
(Enigma) against lldb's own output. Remaining step 2 work (analyst/
write tools) and steps 3-5 (orchestrator, eeacollatz end-to-end
validation, RedRunner blind test) not yet started.

Session 2026-11-04: step 2's remaining analyst/write tools
(mace_set_breakpoint, mace_patch, mace_step_instruction) CLOSED --
all three live-validated on real iOS hardware (Enigma), with two real
LLDB scripting bugs found and fixed via live testing (a stale
SBThread handle reused after a resume/stop cycle; SBThread.
StepInstruction() not blocking until the process actually stops
unless the debugger is forced into synchronous mode). mace_patch
required a new shared src/mace/core/patch_history.py module to avoid
a circular import, unifying the AI-driven and human-driven patch
audit trails into one mace_patch_history output -- confirmed live.
Step 3 (Claude Agent SDK orchestrator) CLOSED as a working stub: new
src/mace/orchestrator/ package plus requirements.txt and a dedicated
.venv-orchestrator virtualenv, wrapping all six channel.py tools as
SDK tools, restricting the agent to exactly those six (not the SDK's
much wider default toolset), and gating the three write-tier tools
behind an interactive y/n confirm. Live-validated end to end: SDK
auth, a read tool cross-checked byte-for-byte against lldb's own
output, both the write-gate deny and approve paths, and audit-trail
unification holding through the full AI-pipeline path. Steps 4-5
(eeacollatz end-to-end validation, RedRunner blind test) not yet
started.

Paste or attach this file at the start of a new chat — with this
assistant, a different LLM, or any capable assistant — to resume MACE
work with full context, without searching through old chat history.
Update this file together with whichever assistant you're using at
the end of every work session — it should always reflect "where
things stand right now," not a full history (that's what ROADMAP.md
and BACKLOG.md are for). A fresh assistant reading this file should be
able to tell current truth apart from superseded investigation notes
immediately — see the dedicated section below for exactly that.

## Mandatory workflow — always follow this
CB edits all files personally via nano; the assistant never edits the
repo directly. For every change:
1. The assistant gives the exact text and identifies the file and
   insertion/edit location.
2. CB opens the file in nano, makes the edit, saves.
3. The assistant gives validation commands (grep/wc/etc) to confirm
   the edit landed correctly.
4. Only after validation passes, the assistant gives the git
   add/commit/push commands.
This applies to ROADMAP.md, BACKLOG.md, docs/, source code — everything,
and to any LLM assistant working the project, not just one specific one.

## Active milestone
- v2: PINNED (2026-09-27) — all three validation targets complete.
- v2.1: CLOSED (2026-10-03) — all three polish items done and
  live-validated (get_long_help() fix, mace_patch_mem, per-platform
  connect automation).
- v2.5: CLOSED (2026-10-31) — EEA/Collatz dual-platform validation
  target (Enigma app, iOS + Android). Checklist status
  (docs/v2.5-mace-validation.md):
  - Item 1 (custom svc dispatch annotation): CONFIRMED, both
    platforms (Android 2026-10-28, iOS 2026-10-31).
  - Item 2 (register state at svc sites): CONFIRMED, both platforms
    (same sessions as item 1).
  - Item 3 (Frida-detection reads 0 under MACE's attach): RETIRED,
    not achievable as written. Investigation (2026-10-30) ruled out
    every code-level and environment-level cause for this device's
    Frida-detection flag always reading "detected" under MACE — root
    cause turned out to be unrelated to MACE's presence (see below).
    CB's call (2026-10-31): drop Enigma's entire Frida-detection path
    rather than keep chasing this, since it wasn't serving the
    validation purpose it was designed for.
  - Item 4 (Swift "you are here" annotation): CONFIRMED, iOS
    (2026-10-31).
  - Item 5 (JNI "you are here" annotation): CONFIRMED, Android
    (2026-10-28).
  - Item 6 (collision walkthrough, secondary goal): CONFIRMED, iOS
    only (real flag + reversed anagram both reach "Access Granted!"
    with identical wrong accumulator values at both comparison
    sites). Deliberately NOT repeated on Android — see cross-platform
    demo decision above.
  Root cause of the iOS opaque-predicate bug: the `charset_ok` block
  in the per-character loop was extra, undocumented noise gated on
  `x28` (the Frida-clean flag), which always read `1` on-device — so
  the noise always executed and corrupted the real accumulators
  before the correct, unconditional accumulation in `char_done` could
  run. Confirmed fixed by removing Enigma's Frida-detection path
  entirely (Cursor implementation, validated 2026-10-31): iOS reaches
  "Access Granted!" with zero MACE patches now.
- Pre-v3 UI cleanup: CLOSED (2026-11-01). Two batches:
  1. Four items originally scoped (2026-10-31 planning session):
     breakpoint-ID sentinel guard, per-image ASLR slide fix,
     `handle_stop` thread-interleaving lock, `mace_options`/
     `mace_help` command listing.
  2. Four additional light-lift items CB approved after asking "any
     other UI improvements that are not heavy lifts": register
     grouping by AAPCS64 role (args/temps/callee-saved), `mace_watch`
     (runtime-configurable watched registers, replacing hardcoded
     WATCH_REGS), compact call-chain context (auto-displayed, capped
     depth), `mace_breakpoints` (breakpoint resolution status/hit
     count panel).
  Plus, raised directly by CB mid-session: full memory-region
  labeling (Context Panel v2 item 3, originally logged 2026-08-30) —
  `_classify_memory_region()` replaces a meaningless raw decimal with
  `[heap/stack]` or `[<module>.<section>]` for address-shaped
  registers.
  All 8 items plus region labeling live-verified on a real eeacollatz/
  Enigma iOS session the same day. Two real findings surfaced during
  that verification, both root-caused and fixed same-session:
  - Call chain was reliable at depth 0-1 but not depth 2+ on this
    binary's optimized Swift unwind (two stops with a byte-identical
    caller frame produced two different, inconsistent values for
    frame #2). Fixed by capping the default depth at 2.
  - Region labeling appeared intermittent at first (same literal
    stack address labeled on one stop, not on the next) — a one-retry
    fix did NOT resolve it. Direct diagnosis via lldb's own `memory
    region <addr>` command revealed the real cause: this specific iOS
    jailbreak debugserver build doesn't support the qMemoryRegionInfo
    packet at all (a hard capability gap, not flakiness).
    `_classify_memory_region()` was gating its module/section
    resolution path — which needs nothing from the remote stub —
    behind that same unreliable query. Fixed by trying module/section
    resolution first; raw heap/stack pointers (not backed by any
    loaded image) will not get a coarse label on a debugserver build
    without qMemoryRegionInfo support, but this is now a documented,
    understood limitation rather than a silent inconsistency. See
    BACKLOG.md's 2026-11-01 entries for full detail and commit
    references.
- Scudo heap-validation candidates: CLOSED as dead ends (2026-10-19).
  N4TIVE's Heap Feng Shui challenge (ch05) uses a custom 8-slot slab
  allocator, not Scudo. The MobileHackingLab candidate uses jemalloc,
  same allocator already ruled out via CENSUS/shadow. No current
  candidate target for Scudo validation — stays open, needs a
  genuinely new find. See BACKLOG.md's "Post-GA Android heap/anti-
  debug/JNI validation candidates" entry for full detail.
- N4TIVE Anti-Debug Gauntlet (ch04) and Type Confusion (ch03): both
  solved end-to-end on the Pixel 10a (ch04 2026-10-20, ch03
  2026-10-21), pure MACE/lldb, no Frida. Confirmed MACE capability
  demonstrations, and now part of the v3 demo lineup (Android's half
  of the cross-platform story, alongside RedRunner). Full detail in
  BACKLOG.md's dated entries.
- v3 (AI + MCP, NowSecure demo target): demo lineup and narrative
  finalized 2026-10-31 (see ROADMAP.md's dated entry) — iOS =
  eeacollatz, Android = N4TIVE ch03/ch04 + RedRunner. Design/
  implementation work started 2026-11-02, now that the pre-v3 UI
  cleanup above is closed.
  - Findings-JSON ingestion sub-feature: CLOSED (2026-11-02). A
    tool-agnostic JSON a static-RE tool could produce, which MACE's
    orchestration layer actually reads and acts on — sets
    breakpoints, annotates the context panel — rides the current
    "Reverse Engineer Anything" moment as the pitch narrative without
    wiring up REA itself. Draft schema in BACKLOG.md's 2026-10-31
    entry; MVP (loader, registry, panel annotation,
    mace_load_findings command) committed and live-validated on iOS
    the same day, both symbol- and address/RVA-resolution paths
    confirmed landing identically (findings/eeacollatz.json).
    Extended same day with `offset` support (symbol + byte offset,
    for a finding that isn't at a function's entry point — found
    necessary while scoping N4TIVE ch04's real patch site) and a
    module-resolution fix (both the address and offset paths had
    assumed the target's main executable was module 0 — true on iOS,
    false on Android, where the real target is always a separately
    dlopen'd .so; now resolves by the findings-JSON's own `binary`
    field instead). Both fixes found and fixed the same session via
    live Android work, not speculative design. findings/n4tive_ch04.json
    (three symbol+offset findings: verify_flag, check_tracer_pid,
    check_ptrace) live-validated end to end on the Pixel 10a,
    including a full real bypass — `mace_patch w8 1` at the
    HMAC-compare gate, continue, and the app's own UI flipped to
    Status: SOLVED with a nonsense input string. One accuracy bug in
    a finding's note text (polarity backwards) caught live and fixed
    same session. Full detail: BACKLOG.md's 2026-10-31 through
    2026-11-02 entries under "Findings-JSON ingestion."
  - Not yet done: N4TIVE ch03 and RedRunner findings JSONs. Rest of
    v3 (AI+MCP architecture) untouched.
  - JEB MCP integration CONFIRMED OUT OF December-deadline scope
    (2026-11-02). Already tagged "stretch goal, Nov or post-GA" in
    ROADMAP.md, and already covered by the existing 2026-10-08
    decision ("Static RE Out of Scope" -- RE assumed done offline,
    via manual work or some other tool's MCP such as Ghidra/JEB/REA,
    with its output consumed as input). Today's findings-JSON
    ingestion work (above) is the concrete implementation of that
    decision and the demo's actual proof point that static analysis
    happened -- no JEB integration needed to make that case. See
    ROADMAP.md's matching 2026-11-02 note for full detail.
  - V3 end-to-end architecture designed 2026-11-03 (ROADMAP.md dated
    entry): four layers (lldb -> MACE MCP channel -> separate MCP
    server process -> Claude Agent SDK orchestrator), with Dec-scope
    decisions (single agent, tool-gated permissions, not three
    separate agent contexts; real enforced human-approval gate via
    the SDK's own permission system; DSPy local/cloud routing
    deferred past Dec; RedRunner deliberately left WITHOUT a
    pre-built findings-JSON, used instead as v3's first genuinely
    blind orchestration test case; N4TIVE ch03 findings-JSON also
    deferred) and four extension seams for GA (model selection behind
    one interface; MCP transport as an abstraction; tool permission
    policy as data; every tool tagged with a tier now even though
    nothing routes on it yet).
  - Step 1 (lldb-side MCP channel) CLOSED (2026-11-03):
    src/mace/mcp/channel.py hosts a Unix domain socket inside the
    live lldb session, newline-delimited JSON protocol
    ({"tool":...,"args":...} -> {"ok":...,"result"/"error":...}),
    dispatched through a tool registry tagged with tier
    (session/diagnostics/analyst) and mode (read/write) metadata.
    New mace_mcp_on/mace_mcp_off commands start/stop it. Known,
    documented limitation: the channel's own lock only serializes
    concurrent MCP calls against each other, not against
    stop_hook.py's handle_stop on the stop-hook thread -- CB's
    explicit call not to fix this for Dec (BACKLOG.md 2026-11-03).
  - Step 2's read-only (diagnostics tier) tool set CLOSED (2026-11-03):
    mace_get_register_context (reuses snapshot_from_frame directly,
    per the JSON-via-direct-calls protocol decision -- no lldb
    command-text scraping), mace_read_memory (capped at 4096
    bytes/request), mace_get_backtrace (capped at 64 frames/request,
    default 32). All three live-validated on real iOS hardware
    (Enigma, collatz_eea_v2_check stop): register context matched the
    mace_on panel exactly across every field; read_memory matched
    lldb's own `memory read` byte-for-byte; get_backtrace's addresses
    matched lldb's own `bt` exactly across all 32 default frames
    (function names differ cosmetically -- full qualified names vs
    bt's short display form -- not a bug).
  - Step 2's analyst/write (write-tier) tool set CLOSED (2026-11-04):
    mace_set_breakpoint (raw load-address convention matching
    mace_read_memory; offset path requires both symbol AND module),
    mace_patch (reuses MACEPatch's SBValue patch-and-readback
    discipline; required a new shared src/mace/core/patch_history.py
    module to avoid a circular import with stop_hook.py, unifying the
    AI-driven and human-driven patch audit trails into the same
    mace_patch_history output), and mace_step_instruction (step-into/
    step-over via SBThread.StepInstruction). All three live-validated
    on real iOS hardware (Enigma). Two real LLDB scripting bugs found
    and fixed via live testing on mace_step_instruction: a stale
    SBThread handle reused across a resume/stop cycle (must re-fetch
    via process.GetSelectedThread() after stepping), and
    SBThread.StepInstruction() not blocking until the process actually
    stops unless the debugger is forced into synchronous mode
    (debugger.SetAsync(False)/restore).
  - Step 3 (Claude Agent SDK orchestrator) CLOSED as a working stub
    (2026-11-04): new src/mace/orchestrator/ package (mcp_client.py,
    tools.py, gate.py, model.py, run.py) plus requirements.txt and a
    dedicated .venv-orchestrator virtualenv (claude-agent-sdk,
    gitignored). Wraps all six channel.py tools as Claude Agent SDK
    tools, restricts the agent's visible tool set to exactly those six
    (via ClaudeAgentOptions(tools=...) -- the SDK's own default
    toolset otherwise includes unrelated built-ins like Agent/Glob/
    SendMessage/CronCreate), and gates the three write-tier tools
    behind an interactive y/n confirm wired as a PreToolUse hook
    (model-selection stubbed as a single hardcoded constant, per the
    Dec-scope decision -- extension seam #1). Live-validated end to
    end on real iOS hardware: SDK auth via an Anthropic Console API
    key, a read tool call (mace_get_register_context) cross-checked
    byte-for-byte against lldb's own register read, both the
    write-gate deny and approve paths (register patch correctly
    blocked on 'n', correctly applied and cross-checked on 'y'), and
    audit-trail unification holding through the full AI-pipeline path
    (the orchestrator-driven patch appears in the same
    mace_patch_history as step 2's direct-socket and human-driven
    patches).
  - mace_continue (7th tool, added 2026-11-05, not in original step-3
    plan): resumes execution and waits for a terminal process state
    (stopped/crashed/exited/detached) via an SBListener-based bounded
    poll (default 30s, hard cap 120s) -- needed to unblock step 4
    once end-to-end testing began and surfaced that the original six
    tools had no way to resume execution at all. Wired through
    channel.py, orchestrator/tools.py, orchestrator/gate.py (added to
    the write-tier gate, same approval flow as the other write tools),
    and orchestrator/run.py. Along the way, found and fixed a real
    LLDB API type-strictness bug (SBListener.WaitForEvent()'s timeout
    argument is a uint32_t, not a Python float) and empirically
    confirmed that mace_on's stop-hook panel fires identically whether
    a resume was triggered by the interactive `continue` command or by
    SBProcess.Continue() called from script code.
  - Register pc/lr/sp/fp hex-formatting usability bug: FIXED
    (2026-11-05). mace_get_register_context, mace_step_instruction, and
    mace_continue all returned these fields as raw decimal ints
    (accurate, but requiring the agent to hex-convert by hand) --
    flagged as a deferred usability item on 2026-11-04, then recurred
    as a real accuracy bug on 2026-11-05 during live step-4 testing
    (the orchestrator's own narration reported wrong PC/LR values).
    Fixed via a new _add_hex_fields() post-processing helper in
    channel.py, adding pc_hex/lr_hex/sp_hex/fp_hex string fields
    alongside the existing decimal ones. Live-validated via the
    orchestrator: narrated PC/LR now match lldb's own panel
    byte-for-byte. See BACKLOG.md's 2026-11-04/05 entry.
  - mace_get_findings and mace_delete_breakpoint (8th/9th tools, added
    2026-11-06): closed the 4 gaps surfaced by the first blind step-4
    run on 2026-11-05 (module filtering on plain-symbol breakpoints,
    no way to remove a too-broad breakpoint, findings-JSON data
    invisible to the orchestrator, client/server timeout mismatch
    causing BrokenPipeError). Each live-validated individually (raw
    socket, then through the orchestrator, then cross-checked
    natively) and committed separately -- see BACKLOG.md's 2026-11-05/
    06 entries for full detail and commit refs (2b7d7e1, ee61ff1,
    3f630bb, 72b315b).
  - Step 4 (end-to-end validation on eeacollatz): CLOSED (2026-11-06).
    A single blind orchestrator prompt ("investigate... check
    mace_get_findings first... get the app to display 'Access
    Granted!'") drove the full chain unaided: called mace_get_findings
    and got the real check_flag breakpoint with zero symbol-guessing
    (the same symbol the 2026-11-05 blind run had guessed among 6
    wrong guesses, now surfaced with a note and suggested_action
    instead of blind luck); continued to the live hit; landed at the
    denied: fail path after a garbage flag ("ffggggyy") failed the
    cmp x20,x0 gate; reasoned past the finding's own suggested_action
    (patch x20 at the comparison site) and instead stepped over the
    `mov w0, #0` and patched x0 -- the AArch64 return-value register
    for the Swift Bool -- from 0 to 1; resumed cleanly. Enigma rendered
    "Access Granted!" (screenshot confirmed by CB). This is the first
    fully successful end-to-end orchestrator-driven run in the
    project, and did not reproduce the deferred MCP-channel/stop-hook
    race (see below) despite an identical mace_continue/step/patch/
    continue sequence to the run that surfaced it on 2026-11-05 --
    suggestive but not conclusive, since the noisy/ambiguous
    breakpoint conditions from that earlier run are exactly what
    mace_get_findings eliminated.
  - Step 5 (RedRunner as first blind orchestration test): ran
    2026-11-07. Surfaced two real findings rather than a demo win --
    see BACKLOG.md for full detail. First, a real MACE/lldb capability
    gap (unconfigured SIGXCPU/SIGPWR pass-through starved mace_continue
    of a terminal state on RedRunner's 76-thread target) was root-
    caused and fixed (commits 24fae50, e6a4b3d, ee236f9) -- verified via
    a clean breakpoint hit through mace_continue. Second, a deeper and
    separate issue surfaced once real gameplay interaction was tested:
    lldb's tracing overhead itself (independent of any signal) is heavy
    enough on this target that Unity's own ~2s pause-lifecycle watchdog
    times out and self-kills the app (confirmed via adb logcat, not
    guessed -- commit 8b8b928). No quick fix exists for this second
    issue. CB's call: demote RedRunner to backlog, replace it in the
    active demo lineup with Allsafe-Android (t0thkr1s/allsafe-android),
    selected over three other evaluated candidates (commit 9939d00).
  - Step 5 CLOSED (2026-11-08) under a reframed conclusion, not as
    originally scoped. Allsafe-Android was built, attached (27
    threads, no SIGXCPU/SIGPWR or tracing-overhead issues), and
    challenge 13 ("Hook the Native") was walked end to end manually
    via plain lldb commands (register write/breakpoint set/c) with
    MACE's observability panel displaying throughout: breakpoint
    chain Java_...checkPassword -> checkPass -> hardcoreEncryption ->
    the real comparison at ___lldb_unnamed_symbol_1ea38, register
    patch of w0 from 0 to 1 at checkPass+72, confirmed via the app's
    own "Wrong password, try harder" toast no longer appearing. Then
    ran the orchestrator fully blind (no findings-JSON, no hints)
    against the same target -- it correctly returned empty from
    mace_get_findings, reasoned from first principles toward common
    comparison-function names (strcmp/strncmp/memcmp/dlopen/
    JNI_OnLoad), and ended in error_max_turns with no hit, because
    the real check is an anonymous local symbol no amount of
    name-guessing can reach. CB's call: this confirms the
    architectural boundary (static analysis -> JSON -> MACE's dynamic
    agent) is correctly drawn, not a gap -- "fully blind, zero input"
    is retired as a validation target/demo mode. See BACKLOG.md's
    2026-11-08 entry for full detail. One open item the manual
    walkthrough surfaced: it used plain lldb commands throughout, not
    MACE's own MCP write-tools (mace_patch/mace_set_breakpoint/
    mace_continue were never called) -- so the "analyst-guided, no
    JSON" tier is not yet proven through MACE's own tool surface, only
    through plain lldb with MACE's panel displaying. Re-ran the
    orchestrator with the symbol names as guidance later the same day
    (2026-11-08): the reasoning was complete and correct through
    MACE's own tools -- it independently derived the real patch point
    (x0=1 at checkPass's final write before ret) -- but the MCP
    channel dropped mid-sequence and the lldb session hung outright,
    requiring kill -9 to recover. A follow-up manual attempt to finish
    the patch via direct socket calls (bypassing the SDK) instead
    destabilized the process a second way (real Android ANRs, from
    interleaving native lldb commands with concurrent MCP-socket
    calls). All three findings are documented in BACKLOG.md's
    2026-11-08 entries, including a likely revision to the RedRunner
    thread-churn root cause (ART's own debugger-aware brk
    instrumentation, not Unity/thread-count-specific). The patch
    itself was never actually applied -- the tier remains unproven
    through MACE's own tool surface, now for an infrastructure
    reason rather than a reasoning one.

## Immediate next work
1. ~~Finish the analyst-guided, no-JSON patch on Allsafe-Android
   challenge 13~~ -- DONE (2026-11-12, BACKLOG.md). Completed through
   MACE's own MCP tool surface (mace_set_breakpoint/mace_patch/
   mace_continue), not just plain lldb -- this is the real "analyst-
   guided, no-JSON" tier validation, now proven end-to-end. Also fixed
   a real bug along the way: MACEStopHook.handle_stop was auto-
   continuing past Android's attach-time SIGSTOP flood (commit
   7ad117a).

   Next: UI improvements -- register-panel ASCII decode, and the
   Swift/ObjC register decoding for the stop-context panel (iOS,
   logged 2026-11-09). Bounded/timeboxed pass, per 2026-11-09's scope
   decision -- RecoveryDemo (the health-metrics app, candidate 4th
   demo / full prototype test case, see BACKLOG.md 2026-11-11/12)
   comes after this and the UI pass, not in parallel.

- N4TIVE ch03 and RedRunner findings JSONs: BOTH deliberately deferred
  (2026-11-03), not scheduled. RedRunner's deferral is permanent by
  design (it's v3's blind test case, item 2 above); ch03's solve
  techniques (direct native-function-call injection, a TOCTOU defeat
  via mid-call breakpoint+patch, a standalone script for gate4) don't
  fit the simple "breakpoint+annotation" findings-JSON model the way
  ch04/eeacollatz did.
- MCP channel lock-scope limitation (channel.py's LLDB_LOCK doesn't
  serialize against stop_hook.py's handle_stop) -- deferred per CB's
  explicit call, BACKLOG.md 2026-11-03 entry.
- tier/mode metadata duplication between channel.py's _TOOLS registry
  and orchestrator/gate.py's hardcoded write-tool list -- documented
  as a known limitation, BACKLOG.md 2026-11-04 entry. Still stands:
  adding mace_continue on 2026-11-05 required manually adding it to
  gate.py's WRITE_TOOLS set too, exactly the kind of manual sync this
  entry warns about.

Deferred, no session currently allocated:
- N4TIVE's remaining challenges not already covered (XOR decryption,
  buffer overflow, custom stack-based VM) — not yet scoped as
  backlog-relevant the way Anti-Debug Gauntlet/Type Confusion are.
- Whether the demo-day debugserver build (NowSecure's own
  environment, or whichever device ends up used) supports
  qMemoryRegionInfo — determines how much of the heap/stack region
  labeling shows up live versus falling back to decimal. Worth
  checking ahead of the actual demo, not just this dev iPad. Now a
  cross-platform question, not just iOS: see the new Android
  qMemoryRegionInfo finding under Device baseline below.
- Alternative heap/stack classification (SP-proximity, malloc_size())
  not dependent on qMemoryRegionInfo at all — parked for after v3,
  BACKLOG.md's 2026-11-01/2026-11-02 entries.

## Validated targets (v2, complete — see ROADMAP.md Priority 1)
- Frida-0x8 — mace_patch register flip, live syscall annotation.
- libantifrida.so — target-independence proof (register-control and
  syscall-decode both confirmed; no visible on-screen bypass effect
  on this particular target, a finding about the app's own checkmark
  logic, not a MACE limitation).
- Unity/IL2CPP (custom SpinCube test app) — full pipeline: from-
  scratch Unity 6.3 LTS build -> Doppelglower Il2CppDumper fork ->
  RVA-based lldb breakpoint -> register read via MACE panel ->
  memory write patch -> confirmed VISIBLE on-device effect (cube
  stopped spinning). Re-validated 2026-10-02 via the new
  mace_patch_mem command against the same live process/address,
  same visible effect. Now internal-only — RedRunner (real
  open-source Unity game) is the v3 demo-facing IL2CPP target
  instead; SpinCube already did its job proving the pipeline
  mechanically.

## Validated targets (v2.1+, complete)
- N4TIVE ch04 "ANTI-DEBUG" Gauntlet (com.ctf.nativectf) — all 7
  checks plus the HMAC-SHA256 flag-verification gate bypassed via
  register patches, full mace_patch_history audit trail.
- N4TIVE ch03 "Type Confusion" (com.ctf.nativectf) — gates 2-4 solved
  via direct native-function-call injection from lldb, zero Frida;
  gate1 via direct state patch after its intended trigger path was
  proven structurally unreachable on this ART build.
- eeacollatz (Enigma, iOS + Android) — see v2.5 checklist status
  above for full detail.

## Known-good debugger recipes (copy-paste, always current)
Full detail and troubleshooting: docs/android-setup.md,
docs/ios-setup.md. This is the fast path — prefer the one-command
forms (mace_connect_android, mace_connect_ios) over the manual
sequences below; the manual sequences remain here for
troubleshooting when a one-command form fails partway.

Known-good host (confirmed 2026-09-25, Frida-0x8 session): Homebrew
lldb 23.1.1. Not re-verified during the 2026-09-27 Unity/IL2CPP
session (plain `lldb` was run without checking which binary resolved)
-- treat Homebrew lldb as the proven choice, and confirm with `which
lldb` / `lldb --version` before assuming Apple's bundled
/usr/bin/lldb behaves identically; that substitution has not been
tested and was flagged in earlier sessions as a real, previously-
uncontrolled variable.
Known-good Android server toolchain: extracted from Android NDK r27d
(LTS), at .../lib/clang/18/lib/linux/aarch64/lldb-server -- i.e. the
NDK's own clang/lldb toolchain version 18, not a standalone
lldb-server release version.
Device baseline: Pixel 10a, Android 16 / API 36, arm64-v8a, Magisk
root. iOS baseline: iPad 7th Gen, A10, iOS 18.7.2, palera1n
semi-tethered jailbreak. This iOS device's debugserver
(`/var/jb/usr/lib/llvm-16/bin/debugserver`, lldb-16.0.0) does NOT
support the qMemoryRegionInfo packet — confirmed 2026-11-01 via a
direct `memory region <addr>` test returning "error:
qMemoryRegionInfo is not supported." Affects only the region-labeling
feature's coarse heap/stack fallback; module/section labels (which
don't need that packet) work normally. Worth re-checking on whichever
device/debugserver build is actually used for the NowSecure demo.

This Pixel 10a's lldb-server shows a different, more confusing
qMemoryRegionInfo profile — confirmed 2026-11-02 during the N4TIVE
ch04 Android session: it DID work (three real breakpoint hits
correctly labeled non-module addresses), then started failing
consistently right after a benign SIGCHLD/fork-stop (same documented
`linker64`/zygote pattern as BACKLOG's 2026-10-20 entry), including
on an address that had been successfully labeled moments earlier in
the same session. CB's observation: yesterday's iOS failure showed a
similar works-then-fails shape but with no correlating fork-stop
event — plausibly a different root cause on each platform (iOS: the
debugserver build genuinely never supports the packet; Android:
possibly the fork event disrupts lldb-server's ability to keep
answering it). Not confirmed as causal, just a correlation observed
once. See BACKLOG.md's 2026-11-02 entry for full detail.

When validating LLDB itself independently of MACE (e.g. isolating
whether a problem is MACE's stop-hook logic or lldb's own behavior),
launch the known-good Homebrew binary with `--no-lldbinit` so MACE's
auto-load doesn't run. Do not use that mode for normal MACE operation
-- only when intentionally testing vanilla lldb.

Android caution, not yet understood: holding an lldb breakpoint open
on a main/UI-thread JNI call (e.g. checkFlag()) for more than ~5s
risks Android's ANR watchdog, and outlasting the ANR dialog has
SIGSEGV-killed the process once. ANR notifications can surface even
after the process has already died — detection is decoupled from
live process state, likely because lldb pausing the main thread for
real wall-clock time queues a watchdog determination independent of
whether the process is still alive by the time it fires. Separately,
a genuine SIGSEGV with an ART-interpreter-only backtrace (no app
frames) has now recurred identically (same registers, same 62-frame
backtrace) across three different days (2026-10-28 x2, 2026-10-30,
2026-10-31 x2) and two different app builds — treat this as a
pre-existing, unrelated ART/lldb interaction, not an app or Frida-
removal regression, unless new evidence says otherwise. Lesson: move
fast through breakpoint stops once inspected, or expect to need a
reattach after any extended pause.

### Android
Layer 1 (device-side prep, no lldb dependency):
`scripts/android_device_prep.sh [port] [local_lldb_server_path]` --
kills stale lldb-server processes, pushes/launches it in platform
mode, sets up the adb forward, all idempotently.

Scripted relaunch/connect (added 2026-10-28, documented in
docs/android-setup.md's Quick Start section 2026-10-30) — not
app-specific, package is always passed in or cached:

    scripts/android_relaunch.sh <package[/activity]>
    scripts/android_connect.sh [package] [pid]

Layer 2 (one lldb command for the full client-side sequence):

    lldb
    (lldb) mace_connect_android <package> [<port>]
    (lldb) mace_on

Manual form (for troubleshooting only — mace_connect_android wraps
all of this):

    lldb
    (lldb) platform select remote-android
    (lldb) settings set platform.plugin.remote-android.package-name <pkg>
    (lldb) settings set target.parallel-module-load false
    (lldb) process handle SIGSEGV -n false -p true -s false
    (lldb) process handle SIGBUS -n false -p true -s false
    (lldb) platform connect connect://localhost:<port>

    adb shell cmd package resolve-activity --brief <pkg>
    adb shell am start -n <pkg>/<ActivityName>
    adb shell pidof <pkg>
    (lldb) process attach --pid <PID>
    (lldb) mace_on

### iOS
Layer 1 (device-prep) stays manual — CB's deliberate choice, since
it's already simple and he wants to catch on-device issues directly:

    ssh root@<ipad-ip>
    /var/jb/usr/sbin/sshd
    export PATH="/var/jb/usr/lib/llvm-16/bin:$PATH"
    ps aux | grep <AppName>
    debugserver 0.0.0.0:1234 --attach=<PID>

Layer 2 (one lldb command for the client-side sequence):

    lldb
    (lldb) mace_connect_ios <ip> [<port>]
    (lldb) mace_on

Manual form (for troubleshooting only):

    lldb
    (lldb) platform select remote-ios
    (lldb) process connect connect://<ip>:1234
    (lldb) mace_on

Note: iOS uses `process connect`, NOT `platform connect` — debugserver
already attaches server-side at launch, so process connect both
connects and creates/attaches the target in one step. This is the
opposite of Android, where platform connect alone does not attach
(process attach --pid does the real work afterward). Mixing these up
was the one bug found while building mace_connect_ios (2026-10-03):
platform connect returned success but left no target, producing
"invalid target, create a target using the 'target create' command."

Reminder specific to a stuck Xcode debugserver attach: Xcode's own
"Detach" doesn't always fully release the process — if MACE's own
debugserver attach fails with "process is already being debugged,"
fully Stop the Xcode run session (not just Detach), then relaunch the
app manually from the device home screen (not via Xcode ⌘R) before
attaching, so no debugger auto-attaches. (2026-10-31)

Reminder specific to rebuild freshness: visible source changes in
Xcode are not proof of an updated binary — check the toolbar build
timestamp (or do a Clean Build Folder) before trusting that a
just-rebuilt app reflects recent source edits. (2026-10-31)

Reminder specific to debugserver lifecycle: `debugserver` launched
the way documented above (one-shot per connection) exits when lldb
quits/detaches on the Mac side — it does NOT stay up to accept a new
connection. After any `quit`/detach, check the iPad terminal and
relaunch `debugserver 0.0.0.0:1234 --attach=<PID>` (same PID, if the
app process itself wasn't killed) before reconnecting. Confirmed live
2026-11-01. Separately, `mace_connect_ios` leaves the process stopped
at the initial attach SIGSTOP — `continue`/`c` is required before the
app's UI becomes responsive again, not just before a breakpoint hit;
forgetting this looked like a broken text field mid-session
(2026-11-01) but was just the paused process.

## Superseded — do NOT follow these as current guidance
Preserved as investigation history in ROADMAP.md/BACKLOG.md, but
wrong or outdated as advice today. Do not re-derive or re-try these:

- "Raw address breakpoints are the only reliable approach on
  Android" — SUPERSEDED 2026-09-25. Platform-mode attach (recipe
  above) makes named-symbol breakpoints reliable. See ROADMAP.md's
  explicit [SUPERSEDED 2026-09-25] tag for the full historical
  context on why this was believed originally.
- `lldb-server gdbserver --attach` mode on Android — do not use.
  Caused an outright lldb-server segfault (NDK toolchain crash) when
  tried 2026-09-27, in this project's own environment. Platform mode
  + `su` is the only launch method proven working here.
- Il2CppDumper mainline release (Perfare, v6.7.46) does NOT support
  IL2CPP metadata v39 (Unity 6.3 LTS's format) — use the
  Doppelglower/Il2CppDumper fork instead, built from source. (If
  RedRunner's Unity version differs, re-check which dumper its
  metadata version actually needs — don't assume this fork applies.)
- A method's file "Offset" (raw byte offset) is NOT the same as its
  "RVA" — lldb's `breakpoint set --shlib <lib> --address <addr>`
  needs the RVA. Using Offset silently produces an unresolved
  "pending" breakpoint with no error.
- `mace_patch` is register-only (SBValue API) and does NOT write
  arbitrary memory addresses — SUPERSEDED as a limitation 2026-10-02:
  use the new `mace_patch_mem <address> <size> <value>` command for
  memory writes (same guardrail/audit-trail pattern as mace_patch),
  not lldb's raw `memory write`.
- `adb shell "su -c '... &'"` without redirecting the backgrounded
  process's output appears to hang — it doesn't, lldb-server/the
  process actually started; adb shell is just blocked on the open
  pipe. Always redirect (`>/dev/null 2>&1`) before the trailing `&`.
  Found and fixed 2026-10-02.
- Using `platform connect` for iOS (mirroring the Android recipe) —
  SUPERSEDED 2026-10-03, never shipped beyond local testing. Use
  `process connect` for iOS; see the iOS recipe note above for why.
- A `breakpoint command add` multi-line entry can silently store a
  literal leading `>` as part of the command text if the entry gets
  interrupted/misreads — SURFACED 2026-10-19 during the N4TIVE
  Anti-Debug Gauntlet session (raw lldb, not mace_patch). `breakpoint
  command list <id>` displays the broken text correctly, which reads
  as "just formatting" rather than the literal stored content it
  actually is — only caught at execution time via `error: Aborting
  reading of commands...`. Prefer `breakpoint command add -o "<cmd>"`
  (single-line form) to sidestep the multi-line entry path entirely.
  See BACKLOG.md's 2026-10-19 update for full detail.
- `disassemble -n <func>` / `disassemble --frame` can mis-resolve a
  function's boundary on this iOS build — SURFACED repeatedly during
  the 2026-10-31 eeacollatz session, root cause the same broken-DWARF
  "GetDIE ... outside of its CU" issue already known elsewhere. Use
  explicit `--start-address`/`--end-address` (or plain named-symbol
  disassembly, when that alone resolves correctly) instead of relying
  on frame/name-based range resolution when the disassembly looks
  truncated or misaligned.
- The `charset_ok` block in Enigma's per-character accumulation loop
  was NOT part of the real flag-check logic, despite looking like it
  gated the accumulation — it was extra, undocumented noise layered
  on top (see v2.5 checklist status above). Now moot: removed from
  Enigma entirely 2026-10-31, along with the rest of the
  Frida-detection path.
- Region labeling's coarse `[heap/stack]` fallback flipping on/off
  for the same literal address across stops — initially suspected as
  `GetMemoryRegionInfo()` network flakiness and "fixed" with a retry
  guard (commit 6e0439c) — SUPERSEDED 2026-11-01. The retry did not
  fix it; the real cause is this iOS device's debugserver not
  supporting qMemoryRegionInfo at all (see device baseline note
  above). Real fix (commit e94b70b) reorders classification to try
  module/section resolution first, which doesn't need that packet.
- Findings-JSON address/offset resolution assuming
  `target.GetModuleAtIndex(0)` is the right module — SUPERSEDED
  2026-11-02. True on iOS (one self-contained app binary, happened to
  be module 0) but false on Android, where the real target library is
  always a separately dlopen'd .so (confirmed live:
  libch04_gauntlet.so at module index 355, app_process64 at 0). Fixed
  (commit 480d384) by resolving the module by name via
  `target.FindModule()` against the findings-JSON's own `binary`
  field instead.

## Key reference docs (read these instead of re-deriving from scratch)
- docs/android-setup.md — full Android lldb-server/connect sequence,
  troubleshooting for every gotcha in the recipe above, plus the
  scripted Quick Start workflow
- docs/ios-setup.md — equivalent for iOS/debugserver
- docs/debugging-playbook.md — accumulated RE technique/judgment rules
- docs/v2.5-mace-validation.md — v2.5 validation checklist, now
  CLOSED (see Active milestone above for final item-by-item status)
- scripts/android_device_prep.sh, android_relaunch.sh,
  android_connect.sh — automated Android device-prep/relaunch/connect
- ROADMAP.md — current priority sequencing (superseded conclusions
  are explicitly tagged inline, not just here)
- BACKLOG.md — parked research threads, feasibility assessments,
  architecture ideas (chronological, search by date or keyword)

## Repo
github.com/cb90999/MACE
