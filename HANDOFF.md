# MACE — Session Handoff

Last updated: 2026-10-21
Repo branch: main
Validated through: N4TIVE's Anti-Debug Gauntlet challenge (ch04,
com.ctf.nativectf) defeated end-to-end on the Pixel 10a — 7 checks +
HMAC flag bypass — now through mace_patch, with a full mace_patch_history
audit trail on record (2026-10-20 rerun superseding the 2026-10-19
raw-lldb pass). N4TIVE's Type Confusion challenge (ch03) also solved
end-to-end, 2026-10-21, pure MACE (no Frida) — gates 2–3 via direct
expr-- native injection, including a new expr -i false + mid-call-
breakpoint technique that deterministically defeats gate3's TOCTOU race;
gate1's intended trigger proven unreachable on this ART build (unchecked
GetStringUTFChars doesn't validate object type) and worked around via
direct state patch; gate4 solved by a standalone script, not an lldb
technique. Full writeup in BACKLOG.md. Android/JNI context-panel
annotation (the "you are here" gap logged 2026-10-21) also built and
validated live on the Pixel 10a as of 2026-10-24 -- first real use of
mace_on's stop-hook panel on Android in this project.
Current milestone: v2.1 CLOSED. Scudo heap-validation candidates
(N4TIVE ch05, MobileHackingLab) both closed as dead ends — neither
uses Scudo. N4TIVE's Anti-Debug Gauntlet and Type Confusion challenge
are both confirmed MACE capability demonstrations. Next real step: not
yet decided.

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
- v2.5: EEA/Collatz dual-platform syscall-annotation target. Source
  materials committed 2026-10-03; porting handoff written for Cursor
  (docs/collatz-eea-v2-porting-notes.md). Cursor's actual iOS/Android
  porting work NOT YET DONE — happens outside this chat, on CB's own
  schedule, no date currently set.
- Scudo heap-validation candidates: CLOSED as dead ends (2026-10-19).
  N4TIVE's Heap Feng Shui challenge (ch05) uses a custom 8-slot slab
  allocator, not Scudo. The MobileHackingLab candidate uses jemalloc,
  same allocator already ruled out via CENSUS/shadow. No current
  candidate target for Scudo validation — stays open, needs a
  genuinely new find. See BACKLOG.md's "Post-GA Android heap/anti-
  debug/JNI validation candidates" entry for full detail.
- N4TIVE Anti-Debug Gauntlet (ch04): defeated end-to-end 2026-10-19 —
  all 7 checks (TracerPid, Frida /proc/self/maps, ptrace self-attach,
  timing, self-BRK-scan, Java debugger, APK signature) plus the
  HMAC-SHA256 flag-verification gate itself, all bypassed via register
  patches at each check's branch-decision point. This was originally
  run with raw lldb (`breakpoint command add` + `register write`), not
  yet a MACE capability demonstration on the record. UPDATE 2026-10-20:
  fully reran through plain lldb `breakpoint set` + mace_patch instead
  (there is no `mace_set_breakpoint` command — that name only exists in
  ROADMAP's future v3 MCP tool list; the real mechanism is lldb's own
  breakpoint-setting plus mace_patch for the register write), with a
  full mace_patch_history audit trail — now a confirmed MACE capability
  demonstration alongside Frida-0x8/libantifrida.so/Unity. Full detail,
  including a double-decoy flag mechanism and a new direct
  function-call-injection technique, in BACKLOG.md's dated 2026-10-20
  entry.

## Immediate next work
1. N4TIVE's Type Confusion challenge — still open, not yet attempted.
   (Anti-Debug Gauntlet rerun through mace_patch is DONE as of
   2026-10-20 — see BACKLOG.md's dated entry for full detail, including
   the double-decoy flag mechanism and the direct function-call-
   injection technique used to test it.)

Deferred, no session currently allocated:
- N4TIVE's remaining challenges not already covered (XOR decryption,
  buffer overflow, custom stack-based VM) — not yet scoped as
  backlog-relevant the way Anti-Debug Gauntlet/Type Confusion are.
- BayatGames/RedRunner — open-source Unity game as a richer IL2CPP
  validation target than the SpinCube test app. See BACKLOG.md's
  2026-09-27 entry.
- Remaining items from BACKLOG.md's "External GUI recommendations
  feasibility assessment" — call-chain context, breakpoint status
  panel, register grouping.
- Configurable watched registers (WATCH_REGS hardcoded) — see
  BACKLOG.md's 2026-10-02 entry.
- Cursor's actual iOS/Android porting work on collatz_eea_v2 — see
  v2.5 status above and docs/collatz-eea-v2-porting-notes.md. Happens
  outside this chat.

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
  same visible effect.

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
semi-tethered jailbreak.

When validating LLDB itself independently of MACE (e.g. isolating
whether a problem is MACE's stop-hook logic or lldb's own behavior),
launch the known-good Homebrew binary with `--no-lldbinit` so MACE's
auto-load doesn't run. Do not use that mode for normal MACE operation
-- only when intentionally testing vanilla lldb.

### Android
Layer 1 (device-side prep, no lldb dependency):
`scripts/android_device_prep.sh [port] [local_lldb_server_path]` --
kills stale lldb-server processes, pushes/launches it in platform
mode, sets up the adb forward, all idempotently.

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

## Key reference docs (read these instead of re-deriving from scratch)
- docs/android-setup.md — full Android lldb-server/connect sequence,
  troubleshooting for every gotcha in the recipe above
- docs/ios-setup.md — equivalent for iOS/debugserver
- docs/debugging-playbook.md — accumulated RE technique/judgment rules
- docs/collatz-eea-v2-porting-notes.md — v2.5 handoff spec for Cursor
- scripts/android_device_prep.sh — automated Android device-prep
  (Layer 1 of connect automation)
- targets/src/collatz_eea_v2.s, collatz_eea_v2_helpers.c — v2.5
  source materials (macOS-native; iOS/Android ports not yet built)
- ROADMAP.md — current priority sequencing (superseded conclusions
  are explicitly tagged inline, not just here)
- BACKLOG.md — parked research threads, feasibility assessments,
  architecture ideas (chronological, search by date or keyword)

Known gap: README.md is stale relative to this file (still describes
Android as "not attempted yet" and MACE as v1) — worth a documentation
pass eventually, not blocking, flagged 2026-09-27, still deferred.

## Repo
github.com/cb90999/MACE
