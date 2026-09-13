## Scope

Direct continuation of this morning's session
(android_named_symbol_reliability_notes.md), which ended honestly
unresolved: named-symbol breakpoint resolution had been proven to
work once, on a plain standalone binary, but could not be reproduced
against the real EEA app, and the reliability gap was left genuinely
open. CB brought an external troubleshooting document
(android-lldb-troubleshooting.md) describing a real, independent
session that resolved the same class of problem against the same EEA
app. This session verified that document's claims live, ourselves,
rather than accepting them on the strength of the document alone.

## Two real, previously-uncontrolled variables identified

1. Host lldb client: confirmed via `which lldb` / `lldb --version` that
   every session this entire project has used Apple's bundled
   `/usr/bin/lldb` (2100.0.17.203), never a separately-installed
   Homebrew build. The troubleshooting document deliberately used
   Homebrew's lldb (23.1.1) instead. CB had already installed this
   separately; confirmed the version matched the document's exactly.

2. Connection mode: every attempt against the real EEA app this
   entire investigation (this morning included) used
   `lldb-server gdbserver --attach` or, for the one working plain-
   binary case, `gdbserver` launch mode. The document's actual
   successful architecture was different: `lldb-server platform`
   mode, `remote-android`'s platform plugin, and critically a setting
   never once tried before:

     settings set platform.plugin.remote-android.package-name <pkg>

   set BEFORE `platform connect`, followed by a normal `am start`
   app launch and `process attach --pid <PID>` (not gdbserver's
   --attach, and not a custom launch).

## Live verification, reproduced ourselves

Full sequence run live, this session, not accepted secondhand:

  adb shell su -c '/data/local/tmp/lldb-server platform --listen 127.0.0.1:5040 --server'
  "$(brew --prefix lldb)/bin/lldb" --no-lldbinit
  (lldb) platform select remote-android
  (lldb) settings set platform.plugin.remote-android.package-name com.mace.eeavalidation
  (lldb) platform connect connect://localhost:5040
  adb shell am start -n com.mace.eeavalidation/.MainActivity
  adb shell pidof com.mace.eeavalidation
  (lldb) process attach --pid <PID>
  (lldb) image list

Result: 428+ real modules populated -- app_process64, libc.so,
libart.so, dozens of real system libraries, live JIT-compiled code
regions, and libeea.so itself at a real, correct (ASLR-randomized)
load address. This is dramatically richer than anything seen
anywhere in this project before, including this morning's own single
success (which only ever showed 2 images).

`image lookup -n validate` resolved directly against libeea.so:
`libeea.so`validate at eea.c:44`, exact address 0x7e8 -- matching the
troubleshooting document's own result precisely. The same lookup also
surfaced dozens of unrelated `validate()` functions across system
libraries (libui.so, libgui.so, 30 matches alone in libGLES_mali.so's
SPIRV validation code) -- vivid, live confirmation of why a bare,
unscoped `b validate` would be dangerously broad, and why the
document's module-qualified breakpoint syntax matters.

Set the properly scoped breakpoint:

  (lldb) breakpoint set -n validate -s libeea.so

Continued, tapped Submit on the device with real input ("yuhygg"),
and the breakpoint fired cleanly:

  Process 4840 stopped
  * thread #1, stop reason = breakpoint 1.1
    frame #0: libeea.so`validate(input="yuhygg") at eea.c:45:25

Full source context visible, real live argument value visible, on the
app's own main thread -- not a background-thread crash, not an ANR.
This is the first, complete, live, self-reproduced (not secondhand)
confirmation of the full pipeline this entire project has achieved:
named-symbol resolution, scoped correctly, firing on a real app,
showing real data.

## A real bonus: Rule 14's SIGSEGV mystery is now explained, not just documented

This morning logged (Rule 14) an unexplained, reproducible SIGSEGV
crash pattern in unrelated background threads (SurfaceSyncGroup,
AsyncTask #1) when continuing past a breakpoint on the real EEA app,
root cause explicitly noted as "not understood."

The troubleshooting document names this directly: ART's JIT compiler
generates routine SIGSEGVs as part of a normal null-check-elimination
technique -- not real crashes, and not something specific to our
setup. Applying the same signal-passthrough treatment already used
for SIGCHLD resolves it:

  (lldb) process handle -s false -n false -p true SIGSEGV

Applied this session alongside the existing SIGCHLD handling; no
SIGSEGV-related stop occurred afterward. This morning's "not
understood" root cause is now understood and fixed, not just logged
as a known risk to route around.

## Status -- a real, concrete fix, correctly scoped

This is genuinely a fix for the SPECIFIC problem investigated across
four sessions (named-symbol resolution reliability against a real
Android app), not a claim that every open Android question is
resolved. What changed, concretely, going forward for any Android app
target:

1. Use Homebrew's lldb, not Apple's bundled /usr/bin/lldb.
2. Use lldb-server PLATFORM mode, not gdbserver mode, for real app
   targets.
3. Set platform.plugin.remote-android.package-name BEFORE connecting.
4. Attach via `process attach --pid <PID>` after a normal `am start`
   launch, not gdbserver's --attach and not a custom launch sequence.
5. Scope breakpoints by module (`-s <lib.so>`) -- bare names can match
   dozens of unrelated system-library functions.
6. Apply signal passthrough for both SIGCHLD and SIGSEGV as standard
   practice on Android sessions, not just when troubleshooting.

Not yet re-tested: whether this exact procedure reproduces reliably
across multiple attempts and multiple targets, or whether it shares
any of the same session-degradation fragility found with the
gdbserver-mode approach this morning. Worth deliberately re-verifying
next session before fully retiring the "not yet reliable" framing --
but this is a real, independently-corroborated, live-reproduced result,
not a hopeful theory.
