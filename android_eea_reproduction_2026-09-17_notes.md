# Android EEA Reproduction Session — 2026-09-17

## Scope

Explicit goal for today: determine whether the 2026-09-13 platform-mode
named-symbol-resolution fix (android_platform_mode_resolution_notes.md)
is *reliably reproducible*, not just a one-time success — before moving
to Frida-Labs Challenge 0x8 as a second, independent target. This is a
direct continuation of the reliability question that fix's own writeup
left explicitly open.

## Result, up front

The core fix reproduced successfully, twice in one session, on a fresh
device state. Real breakpoint hit, full backtrace, full register state,
matching the original session's result:

    frame #0: libeea.so`validate(input="ytyyyyyyfr") at eea.c:45:25
    frame #1: libeea.so`Java_com_mace_eeavalidation_MainActivity_checkInput at eea.c:68:18
    frame #2: libart.so`art_quick_generic_jni_trampoline + 148
    frame #3: libart.so`art_quick_invoke_stub + 616

But getting there was NOT clean the way the 2026-09-13 session was —
three distinct new failure modes surfaced along the way, all now
understood and fixed. Honest framing: the underlying named-symbol
resolution mechanism itself is confirmed reliable; the surrounding
session hygiene (device permissions, stale process cleanup, ANR
handling) was not previously documented and cost real time today.

## New failure mode 1 — `su -c` is required at ATTACH time, not just discovery

First attempt today ran `lldb-server platform --listen ... --server`
without `su -c`. `platform select` / `settings set` / `platform
connect` all succeeded normally (the discovery/listening layer doesn't
need root) — but `process attach --pid <PID>` failed with
`error: attach failed: lost connection`. Root was never actually
missing from the original 2026-09-13 recipe (it used
`adb shell su -c '...'` throughout) — today's first attempt simply
omitted it when transcribing the recipe from memory rather than
re-reading the source notes first, which is itself the real lesson:
re-read the primary source before reproducing, don't reproduce from
summary/memory.

**Fix:** always start `lldb-server` via `adb shell su -c '...'`, never
plain `adb shell '...'`, for any session where `process attach` will
be used.

## New failure mode 2 — stale/orphaned `lldb-server` processes destabilize later attempts

After the first attach failure, a second `lldb-server platform`
instance was started (this time correctly with `su -c`) without
killing the first. By the time of the third restart attempt,
`adb shell ps -A | grep lldb-server` showed FOUR processes still
resident: two live listeners bound to overlapping state, a zombie
child (`Z` state) from the failed first attach, and one active child
from the second session. Real, credible source of at least some of
the day's connection instability — multiple servers/orphaned tracers
competing for the same device-side attach machinery.

**Fix:** before starting a fresh `lldb-server platform` session,
always check for and kill any pre-existing instances:

    adb shell ps -A | grep lldb-server
    adb shell su -c 'kill -9 <all listed PIDs>'
    adb shell ps -A | grep lldb-server   # confirm empty

Treat this as standard session-start hygiene, not just incident
recovery — the same spirit as Rule 13/14's "standard practice, not
just troubleshooting" framing for signal handling.

## New failure mode 3 (real, previously undocumented behavior, not a bug) — breakpointing `validate()` reliably triggers Android's ANR dialog

`validate()` is called synchronously on the app's main thread, from
the JNI `checkInput` handler wired directly to the Submit button's
click handler. When lldb pauses the main thread at the breakpoint,
the thread is — correctly and expectedly — unresponsive to Android's
input/health-check watchdog, which surfaces "EEA Validation isn't
responding" with Close app / Wait options. This happened on both
successful reproduction attempts today, and did NOT happen (or at
least isn't mentioned) in the original 2026-09-13 session — the
difference from that session isn't understood, but the ANR itself is
a natural, expected consequence of freezing a thread the OS is
actively polling for responsiveness, not evidence of anything actually
wrong.

**Handling:** tap **Wait**, never "Close app" — this keeps the process
alive long enough to inspect state (`bt`, `register read`, etc.) before
`continue`-ing normally. Confirmed today that a paused main thread does
NOT mean a hung/crashed process — `process interrupt` + `thread list`
during one such ANR showed thread #1 sitting cleanly in
`__epoll_pwait` (normal idle wait, not a real hang), and after
`continue`, the breakpoint fired correctly moments later.

## New failure mode 4 — connection drop specifically after continuing past a `fork` stop, recovered per Rule 10

After confirming the breakpoint hit and pulling backtrace/register
data, `continue` produced a new, previously-unseen stop reason:
`thread #40 ... stop reason = fork` (inside `linker64`'s
`ElfReader::Load`) — some new thread/child spawned mid-session,
unrelated to `validate()`. Continuing past THAT stop is what produced
`Process 26948 exited with status = -1 (0xffffffff) lost connection`.

Checked device state immediately after: `adb shell ps -T -p <pid>`
showed **all ~40 threads** in job-control-stopped state (uppercase
`T`), not the more fragile ptrace-trace state (lowercase `t`) Rule 10
also describes — the less severe of the two cases that rule documents.
Recovered cleanly with:

    adb shell su -c 'kill -CONT <pid>'

App immediately un-froze, ran `validate()` to completion on its own,
and displayed "Bad flag" normally — full recovery confirmed, ANR
stopped recurring.

Root cause of the connection drop itself (why resuming past a fork
event specifically kills the platform-mode session) is NOT understood
yet — flagged honestly as an open question, distinct from the
already-documented SIGCHLD/SIGSEGV signal-handling gaps. Worth adding
`process handle` treatment for fork-related stops as a future
experiment, but not yet tried.

## Status — reliability question: partially answered, honestly

The named-symbol resolution mechanism itself (Homebrew lldb + platform
mode + package-name setting + `process attach` after `am start` +
module-scoped breakpoint) reproduced successfully twice today, on a
freshly launched process each time, after the above operational issues
were cleared. That's real, incremental evidence toward "reliable," not
"proven reliable" — the operational friction around it (root
permission discipline, stale-process cleanup, fork-stop connection
loss) is real and newly documented, not resolved away. Next reproducer
(this session or a future one) should apply all four fixes above from
the start and see whether the FIRST attempt goes clean, rather than
needing the same recovery sequence again.

Next planned step per today's agreed sequencing: Frida-Labs Challenge
0x8 (`com.ad2001.frida0x8`) as the second, independent validation
target, applying this session's full lesson set from the start.

## Bonus, beyond today's original scope — MACE's own context panel fires on Android for the first time

Everything above tested the raw lldb connection/attach/breakpoint
mechanism only (`--no-lldbinit` was used deliberately, meaning MACE
itself was never loaded). Per README.md, Android support was
previously listed as "architecture is designed to accommodate... but
no Android target has been attempted yet" — i.e. this had never been
tried at all before today.

Once the PYTHONPATH fix (see below) let MACE's `.lldbinit` import
cleanly, `mace_on` was enabled after the same attach/signal-handling/
breakpoint sequence, then `continue` triggered a real submit on the
device. MACE's stop-hook fired and rendered a real context panel,
live-confirmed on-screen (not just via pasted text, which had shown a
garbled artifact from the live-redraw terminal — the actual screen
was clean):

    -- Thread 1
    ── MACE  app_process64  breakpoint 1.1  (stop #1)  slide=... offset=...
    ── registers ──
      x0  ...
      x1  ...
    -- Thread 5
    ── MACE  app_process64  breakpoint 18446744073709551615.1  (stop #2)  ...
    ── registers ──
      x0 through x17 ...
    Process 28727 stopped
    * thread #1, ... stop reason = breakpoint 1.1
        frame #0: libeea.so`validate(input="ttfggggggg") at eea.c:45:25
    ...
    app_process64 │ eea.c:45:25 │ breakpoint 1.1

Confirmed live on CB's actual terminal: clean, legible rendering,
proper source-line mapping, MACE's persistent status bar at the
bottom working correctly. This is a real, first-time, positive result
for MACE's own tooling on Android, not just the underlying lldb
connection.

One real, likely-genuine cosmetic bug identified, not yet fixed:
Thread 5's panel header shows `breakpoint 18446744073709551615.1` --
that number is `UINT64_MAX` (a sentinel/invalid value), almost
certainly because Thread 5 didn't itself hit the breakpoint (LLDB's
default behavior stops ALL threads when any one thread hits a
breakpoint -- expected per Rule 2) but MACE's panel code still tries
to render a breakpoint-ID label for it rather than recognizing "this
thread is merely paused, not the one that stopped for a real reason."
Android's much higher thread count (40 vs. anything tested on iOS)
makes this far more visible than it likely ever was on iOS. Not yet
confirmed whether this is Android-specific or a latent gap that iOS
sessions simply never triggered (fewer incidentally-stopped threads
per stop event). Worth a follow-up fix: skip or clearly label panels
for threads whose stop reason isn't a genuine breakpoint/signal hit.

## PYTHONPATH fix (new, first-time-seen issue, unrelated to connection recipe)

Launching Homebrew lldb with the normal `.lldbinit` (i.e. without
`--no-lldbinit`) failed today with:

    ModuleNotFoundError: No module named 'mace'

on both `stop_hook.py` and `trace_mode.py`'s imports. Root cause:
Homebrew lldb's Python interpreter doesn't have `src/mace` on its
`sys.path` by default. Fixed by exporting PYTHONPATH before launching:

    export PYTHONPATH="/Users/chidabangalore/Documents/MACE/src:$PYTHONPATH"

This resolves the BACKLOG.md Toolchain item "Portable path resolution
(replace hardcoded _MACE_SRC)" -- worth a permanent fix (e.g. baked
into `.lldbinit` itself, or a `.macerc` session config per that same
backlog item) rather than needing to be set manually every session.
