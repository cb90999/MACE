# MACE — Session Handoff

Last updated: 2026-11-01
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
Current milestone: pre-v3 UI cleanup CLOSED (2026-11-01) — 8 UI/
discoverability fixes plus full memory-region labeling implemented,
committed, and live-verified on eeacollatz/Enigma (iOS); two real
findings surfaced during live verification were root-caused and
fixed the same session (see Active milestone below for full detail).
v3 AI+MCP design/implementation starts next session, 2026-11-02.

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
  implementation work starts 2026-11-02, now that the pre-v3 UI
  cleanup above is closed. Includes a new scoped feature: findings-JSON
  ingestion (a tool-agnostic JSON a static-RE tool could produce,
  which MACE's orchestration layer actually reads and acts on —
  sets breakpoints, annotates the context panel — rides the current
  "Reverse Engineer Anything" moment as the pitch narrative without
  wiring up REA itself). Draft schema and minimum viable scope in
  BACKLOG.md's 2026-10-31 entry.

## Immediate next work
1. v3 AI+MCP design/implementation, starting 2026-11-02 — pre-v3 UI
   cleanup (above) is done; this is now the only item on deck.

Deferred, no session currently allocated:
- N4TIVE's remaining challenges not already covered (XOR decryption,
  buffer overflow, custom stack-based VM) — not yet scoped as
  backlog-relevant the way Anti-Debug Gauntlet/Type Confusion are.
- Whether the demo-day debugserver build (NowSecure's own
  environment, or whichever device ends up used) supports
  qMemoryRegionInfo — determines how much of the heap/stack region
  labeling shows up live versus falling back to decimal. Worth
  checking ahead of the actual demo, not just this dev iPad.

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
