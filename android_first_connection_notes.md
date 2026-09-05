## Scope for today

Priority 1, item 1 from the v2 scoping session: get lldb-server talking
to the Pixel 10a at all. This is the direct Android equivalent of the
very first debugserver connection to the iPad — the foundation
everything else in v2 depends on.

## NDK setup

r28c does not exist (a search result gave this as "current stable" —
wrong; corrected by CB from Google's own actual downloads page). Real
current releases: r27d (LTS) and r29 (latest Stable). Chose r27d,
Google's own conservative long-term-support designation, since this
is a one-time binary extraction, not active native development.

Real friction worth noting for next time: the macOS NDK package is a
DMG containing an .app-bundle-shaped folder (AndroidNDK<version>.app)
that looks like a normal Finder app but isn't one — double-clicking it
does nothing (no installer runs). The correct move is copying it out
via `cp -R` to a permanent location, same as dragging an app to
Applications, then finding the real content nested under
Contents/NDK/ inside the bundle.

lldb-server binary (aarch64, confirmed via `file`: ELF 64-bit LSB
executable, ARM aarch64, statically linked — no missing shared-library
dependencies to worry about on-device) found at:
  Contents/NDK/toolchains/llvm/prebuilt/darwin-x86_64/lib/clang/18/lib/linux/aarch64/lldb-server

## First connection — real, clean success

Pushed to /data/local/tmp/lldb-server (the standard writable-without-
extra-permissions location on Android), chmod 755, launched via
`lldb-server platform --server --listen '*:1234'` through `adb shell
su -c` (root required — confirmed via Magisk su earlier, context
u:r:magisk:s0). Forwarded via `adb forward tcp:1234 tcp:1234` (USB,
not WiFi IP — deliberately avoiding the exact "device IP changed
mid-session" pain the iPad gave this project more than once).

`lldb`'s own `platform list` was used to find the correct platform
name directly rather than guess from memory (`remote-android`,
confirmed real and correct, unlike the earlier real mistake with the
NDK version number) -- worth normalizing: ask the tool itself for
authoritative answers rather than trust recall, whenever the tool can
just tell you.

  (lldb) platform select remote-android
  (lldb) platform connect connect://localhost:1234
    Platform: remote-android
      Triple: aarch64-unknown-linux-android
  OS Version: 36 (6.1.145-android14-11-gfa1d6308d1fe-ab14691759)

First-try, clean success — Triple and OS Version both independently
confirm what `getprop` already told us (arm64-v8a, API 36/Android 16).
The real Android equivalent of the very first debugserver attach.

## First real attach — netd, and immediate multithreaded stress-test

Attached to netd (PID 879, a stable system network daemon) via
`process attach -p 879`. Immediately surfaced something no iOS target
this project ever presented: **15+ concurrently active threads**, real
names (netd, several binder:879_N, NFLogListener, doh-handler) —
genuinely busier than any iOS target, which mostly had one thread of
real interest.

Set a software breakpoint at 0x74903b4248 (a real, already-frozen
"svc #0" site several threads had independently converged on at
attach time) and confirmed the whole stop-hook/panel pipeline handles
this correctly: 7 threads hit the SAME address simultaneously, each
produced its own correctly-separated panel with genuinely distinct
register state, "-- Thread N" headers and "stop #1" through "stop #7"
incrementing correctly across threads. The signed-reinterpretation fix
from Thursday worked correctly on entirely new content on its first
real exposure (x11 = 0xfffffffffffffff0 -> "(-16i)").

One real, honest cosmetic gap found: the panel showed "MACE unknown
breakpoint 2.1" instead of a real process/binary name, and lldb's own
summary showed "Target 0: (No executable module.)" -- a raw PID
attach has no associated main executable module the way every iOS
target (attached via debugserver to a named app) always did. Not
fixed today; worth a real look whenever binary-name resolution in
snapshot_from_frame gets touched again for Android specifically.

## Linux syscall annotation — built, tested, real ground truth used

Fetched the actual, complete, current ARM64 syscall table directly
from arm64.syscall.sh (already logged as a resource two days ago) --
deliberately did NOT trust memory for this, since ARM64 uses a
distinct, modern numbering scheme genuinely different from the far
better-known x86_64 table (openat=56 here vs 257 on x86_64, read=63
here vs 0 on x86_64 -- memory would very likely have been wrong).

Real, concrete confirmation this was worth doing precisely: x8=0x49
(73 decimal) appeared identically across FIVE separate netd thread
stops in today's own live data, before any code existed to decode it.
Per the real table, 73 = ppoll -- exactly the behavior expected from a
network daemon's normal event loop (waiting on file descriptors with
a timeout). Real, live-observed validation data in hand before writing
a single line of the actual feature.

Implementation mirrors the XNU syscall annotator's exact shape
(_is_linux_syscall_site / _annotate_linux_syscall / LINUX_SYSCALLS
table), reusing ContextSnapshot's existing syscall_name/syscall_kind
fields (kind="Linux") rather than adding new ones -- the existing
panel rendering code needed zero changes to display this correctly.

One important, easy-to-get-wrong detail, deliberately tested for:
XNU's convention is "svc #0x80"; Linux's is "svc #0" -- and the string
"0x80" literally CONTAINS the character "0", so a naive substring
check (the style used for the original XNU detector) would have
incorrectly matched both conventions on the same instruction shape.
Fixed with an exact-match check instead
(operand.strip().lstrip("#").strip() == "0", not `"0" in operand`).

7 mock tests written, including two explicitly "critical" ones
checking mutual exclusivity in BOTH directions (an XNU #0x80 site
must never trigger the Linux annotator; a Linux #0 site must never
trigger the XNU one) -- both passed. A real, genuine bug was caught
DURING test-writing, not by the tests catching a code defect: the
curated LINUX_SYSCALLS table was missing 73 (ppoll) entirely, despite
it being the literal motivating example just found in real data --
a simple, human oversight (got excited about finding the real example,
then forgot to actually add it to the table), caught immediately by
the test's own assertion rather than shipped silently. Fixed before
commit. Full existing XNU regression suite re-run and confirmed
unaffected by any of today's changes.

## Two real operational incidents -- the actual cost of today, and the real lessons

### Incident 1: ANR after an improper stop

Ctrl+C on the lldb-server terminal only kills the client-visible
process, not automatically the debug session's control over the
target -- exactly like every prior orphaned-process incident this
project has hit, but this time with real consequences: netd's threads
were left in state T (stopped by job-control signal) after the
server was killed, and the device surfaced a genuine "App Not
Responding" dialog. Recovered cleanly via `kill -CONT 879` --
confirmed via `ps -T -p 879` showing all threads back to S (sleeping,
normal) immediately after.

### Incident 2: netd crash, real auto-restart recovery

After the SECOND freeze (during troubleshooting for the "no panel
despite trace stop reason" mystery -- see below), netd's threads were
found in state t (LOWERCASE -- specifically "stopped under active
ptrace tracing," a meaningfully different, more serious state than
uppercase T's plain job-control stop). Killed the orphaned tracer
processes directly (the correct move for this state -- a dying
tracer should trigger an automatic kernel-level detach of everything
it was tracing) -- but netd's PID (879) disappeared entirely
afterward, i.e. it crashed rather than cleanly resuming.

Real, working safety net confirmed: Android's init automatically
relaunched netd under a fresh PID (21147) within seconds -- exactly
the resilience a core system service is supposed to have. Confirmed
full recovery via a real ping test (0% packet loss, real RTTs) and a
visual device check. No lasting harm, but a real, concrete cost from
choosing a stateful system daemon as an early debugging target.

### The actual root cause behind BOTH the "no panel despite trace stop
reason" mystery AND (probably) a fair amount of today's friction:
lldb-server's platform mode spawns a brand-new, separate gdbserver
CHILD PROCESS on an unpredictable, dynamically-assigned port for
every real attach/debug session -- confirmed directly by finally
enabling --log-file/--log-channels logging (a real, concrete fix in
its own right -- lldb-server is silent by default in EVERY mode,
confirmed earlier the same day with gdbserver mode too):

  < 21> read packet: $qLaunchGDBServer;
  < 25> send packet: $pid:20438;port:34313;

Only port 1234 (the platform port) was ever forwarded via adb
forward. The actual debugging channel doing the real work -- the one
MACE's stop-hook and breakpoint code actually depends on -- was
running on a completely different, never-forwarded port the entire
day. This plausibly explains every "breakpoint resolves, some threads
show trace, but no panel ever renders" mystery hit today, not a
MACE Python logic bug at all.

## Status

Real, substantial progress: first-ever Android platform connection
(clean, first try), first-ever multithreaded stress test of the
panel/stop-hook pipeline (harder than anything iOS presented, passed
cleanly), Linux syscall annotation fully built and unit-tested against
real, live-observed ground truth (ppoll, x8=73). NOT achieved today:
live confirmation of the syscall annotation firing on real hardware --
blocked by the dynamic-port discovery, not by anything wrong with the
annotation code itself.

Real, well-understood plan for next time, not an open question:
1. Switch from lldb-server platform mode to plain gdbserver mode with
   a direct --attach=<pid> (the same shape as debugserver --attach
   used successfully every single time on iOS this whole project) --
   a fixed, known, single port for the whole session, no dynamic
   child spawning, genuinely scriptable the same way iOS was.
2. Never attach to a live system daemon (netd or equivalent) again.
   Use disposable, purpose-built test targets only -- exactly what
   the original Priority 1 scoping already called for ("one real
   MASTG Android target," mirroring iOS's own discipline of only ever
   using purpose-built test apps -- LocalAuthTest, DVIA-v2, iGoat,
   UnCrackable -- never a real system process). Today's incidents are
   real, if costly, confirmation of exactly why that original plan
   was right, not a reason to change it.
3. Always `process detach` from the lldb client BEFORE touching the
   lldb-server terminal at all, going forward -- the direct,
   correct-order fix for Incident 1.
4. Keep --log-file/--log-channels enabled on lldb-server by default
   going forward -- it's what actually surfaced today's real root
   cause; silence-by-default cost real diagnostic time earlier in the
   day before this was turned on.

## Four questions answered at end of session, worth recording as durable decisions

**Can the lldb-server launch be scripted, like iOS?** Yes -- and the
fix above (switch to gdbserver --attach mode) is what actually makes
this practical, since platform mode's unpredictable per-attach port
can't be pre-scripted around at all.

**Port forward vs. direct device IP?** Staying with USB port-forward
-- avoids the exact "device IP changed mid-session" pain the iPad
gave this project repeatedly. Doesn't fix today's actual bug either
way (that's a platform-mode-specific issue, orthogonal to how the
connection is reached) -- once on gdbserver --attach mode this
question mostly resolves itself (one fixed port, no ambiguity).

**Do we need a scaffolding Android app for MACE work?** No -- today's
whole incident is real, live evidence for why the ALREADY-AGREED
Priority 1 plan (one real MASTG Android target, disposable test apps
only) was correct from the start. Nothing needs to be built; the
Frida-Labs practice APKs and MASTG Android crackmes already logged
are the right kind of target, immediately available.

**Did Android 16 / Pixel 10a hurt us -- should we drop to an older
emulator instead?** No. Both real incidents trace to workflow choices
(platform mode's dynamic ports; netd's fragility under a freeze) that
are properties of lldb-server's own architecture and "any actively-
serving system daemon," respectively -- not properties of this
specific OS version or hardware. An older emulator would relocate the
identical bugs into a different environment while abandoning the
real, already-committed December scope for no actual benefit. Staying
on Android 16 / Pixel 10a; fixing this at the workflow level.
