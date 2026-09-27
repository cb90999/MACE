# MACE — Session Handoff

Last updated: 2026-09-27
Repo branch: main
Validated through: Unity/IL2CPP SpinCube (third validation target)
Current milestone: v2 pinned; v2.1 next

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
- v2.1: polish bucket, next up, starting 2026-10-01.
- v2.5: EEA/Collatz work, planned after CB's 2026-10-12 return.

CB is unavailable for MACE work after 2026-09-27 until approximately
October 12 (surgery recovery) — EXCEPT October 1-4, which are open.

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
  stopped spinning). The strongest of the three validations.

## Known-good debugger recipes (copy-paste, always current)
Full detail and troubleshooting: docs/android-setup.md,
docs/ios-setup.md. This is the fast path.

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
root.

When validating LLDB itself independently of MACE (e.g. isolating
whether a problem is MACE's stop-hook logic or lldb's own behavior),
launch the known-good Homebrew binary with `--no-lldbinit` so MACE's
auto-load doesn't run. Do not use that mode for normal MACE operation
-- only when intentionally testing vanilla lldb.

### Android
Platform mode + `su` is the only workflow currently proven working in
the MACE Pixel 10a / Android 16 test environment (not a universal
claim about lldb-server on Android generally):

    adb push lldb-server /data/local/tmp/lldb-server
    adb shell chmod 755 /data/local/tmp/lldb-server
    adb shell "su -c 'ps -A | grep lldb-server'"   # kill any stale PIDs first
    adb shell "su -c '/data/local/tmp/lldb-server platform --listen 0.0.0.0:10500 --server &'"
    adb forward tcp:10500 tcp:10500

    lldb
    (lldb) platform select remote-android
    (lldb) settings set platform.plugin.remote-android.package-name <pkg>
    (lldb) settings set target.parallel-module-load false
    (lldb) process handle SIGSEGV -n false -p true -s false
    (lldb) process handle SIGBUS -n false -p true -s false
    (lldb) platform connect connect://localhost:10500

    adb shell cmd package resolve-activity --brief <pkg>
    adb shell am start -n <pkg>/<ActivityName>
    adb shell pidof <pkg>
    (lldb) process attach --pid <PID>
    (lldb) mace_on

### iOS
    ssh root@<ipad-ip>
    /var/jb/usr/sbin/sshd
    debugserver 0.0.0.0:1234 --attach=<PID>

    lldb
    (lldb) platform select remote-ios
    (lldb) process connect connect://<ip>:1234
    (lldb) mace_on

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
  Doppelglower/Il2CppDumper fork instead, built from source.
- A method's file "Offset" (raw byte offset) is NOT the same as its
  "RVA" — lldb's `breakpoint set --shlib <lib> --address <addr>`
  needs the RVA. Using Offset silently produces an unresolved
  "pending" breakpoint with no error.
- `mace_patch` is register-only (SBValue API) — it does NOT write
  arbitrary memory addresses. Use lldb's own `memory write` for that
  today (a dedicated `mace_patch_mem` command is planned — see v2.1
  bucket below).

## Immediate next work — v2.1 polish bucket
See BACKLOG.md's "v2.1 polish bucket (2026-09-27)" section for full
detail. In rough order of effort:
1. Fix `get_long_help()` missing on all 7 class-based MACE commands in
   src/mace/lldb/stop_hook.py (mechanical, low-risk, high payoff —
   docstrings already exist, just aren't wired up).
2. `mace_patch_mem` — a memory-write patch command mirroring
   `mace_patch`'s guardrails (stopped-process check, read-back
   confirmation, shared audit trail with a kind: register/memory tag).
3. Per-platform connect automation — a device-prep shell script +
   a single `mace_connect_ios`/`mace_connect_android` lldb command
   per platform (NOT unified — see BACKLOG.md's 2026-09-14 "who
   performs the attach" entry for why). Would encode the recipes
   above into one command each.
4. (optional, after 1-3) BayatGames/RedRunner — open-source Unity
   game as a richer IL2CPP validation target than the SpinCube test
   app. See BACKLOG.md's 2026-09-27 entry.
5. (optional, already sequenced into 1-3 where applicable) remaining
   items from BACKLOG.md's "External GUI recommendations feasibility
   assessment" — call-chain context, breakpoint status panel,
   register grouping.

## Key reference docs (read these instead of re-deriving from scratch)
- docs/android-setup.md — full Android lldb-server/connect sequence,
  troubleshooting for every gotcha in the recipe above
- docs/ios-setup.md — equivalent for iOS/debugserver
- docs/debugging-playbook.md — accumulated RE technique/judgment rules
- ROADMAP.md — current priority sequencing (superseded conclusions
  are explicitly tagged inline, not just here)
- BACKLOG.md — parked research threads, feasibility assessments,
  architecture ideas (chronological, search by date or keyword)

Known gap: README.md is stale relative to this file (still describes
Android as "not attempted yet" and MACE as v1) — worth a documentation
pass eventually, not blocking, flagged 2026-09-27.

## Repo
github.com/cb90999/MACE
