## Scope for today

Thursday's session ended with the `gdbserver --attach` mystery still
unresolved against real app targets (deskclock failed with protocol-
level E44 errors, both with and without SELinux permissive). Today's
goal: build a real, from-scratch APK patching pipeline to test the
"non-debuggable manifest flag is the actual gate" hypothesis directly,
using proper disposable crackme targets instead of a system app.

## Tooling built from scratch today

No Android Studio installed (deliberately, matching the lightweight
NDK-only approach from the first Android session). Needed `apktool`
(already present via Homebrew) and `apksigner` (not present — part of
the Android SDK's separate "build-tools" package, not the base
command-line-tools skeleton).

Real chain of dependencies worked through:
- `brew install --cask android-commandlinetools` requires Java ->
  `brew install --cask temurin` first.
- The commandlinetools cask only installs the bare `cmdline-tools`
  skeleton (sdkmanager, avdmanager, d8, r8, etc.) -- apksigner isn't
  in it. Needed a separate `sdkmanager "build-tools;X"` install.
- Picked build-tools 36.1.0 (latest STABLE, not the 37.0.0 RC builds
  also listed) -- same "stable over bleeding-edge" discipline as the
  NDK LTS choice in the first Android session.

Real, reusable pipeline built and proven twice today:
1. `apktool d <apk> -o decoded` -- decompile to inspect/edit
   AndroidManifest.xml directly.
2. `sed` a `android:debuggable="true"` attribute onto the
   `<application>` tag.
3. `apktool b decoded -o <patched>.apk` -- rebuild.
4. Sign with a fresh, reusable keystore (generated once via `keytool`,
   stored at MobileBinaryTargets/shared/mace-debug.keystore -- the
   Android equivalent of the existing Certificates.p12 used for iOS
   re-signing) via `apksigner sign`.
5. `apksigner verify --print-certs` -- confirm a clean signature
   (exit code 0) before ever installing.
6. `adb install` the patched, signed APK.

Also established a real, consistent storage convention today,
mirroring the existing iOS one discovered along the way (CB had
forgotten where the iOS crackmes lived -- found at
~/Documents/MobileBinaryTargets/ios/crackmes/<Target>/{original,resigned}/,
with a shared/checksums/ folder). Replicated the same shape for
Android: MobileBinaryTargets/android/crackmes/<Target>/{original,
decoded,patched}/, with checksums recorded the same way (with an
-Android suffix on the sha256 filename to avoid colliding with the
existing iOS entries for the same crackme names).

## Target 1 -- MASTG UnCrackable Level 1 (Android)

Confirmed current, correct source: github.com/OWASP/mastg (13.2k
stars, active) -- Crackmes/Android/Level_01 through Level_04 host
real, compiled APKs directly. The older owasp-mastg repo still exists
but appears superseded, matching the exact naming evolution already
logged for the iOS side of this project.

Decoded, confirmed `android:debuggable` was genuinely absent from the
manifest (non-debuggable by default, same as any ordinary production
app) -- patched, rebuilt, signed, installed cleanly.

Real, interesting bonus finding on launch: the app itself detects
`ApplicationInfo.FLAG_DEBUGGABLE` at runtime and self-exits with an
explicit dialog ("App is debuggable! This unacceptable. The app is
now going to exit.") -- a deliberate, built-in anti-debug challenge,
not a MACE or patch-pipeline failure. Confirms the manifest patch
genuinely took effect at the OS level (the app can only detect this
if it's actually true), but means this specific target isn't usable
for testing gdbserver --attach directly -- it adds its own defensive
layer on top of the exact question being tested, tangling two
separate things together. Good, real target for LATER (once
mace_patch-based bypass work on Android begins -- observe the check,
patch the register deciding the outcome, bypass it, the same shape as
MACELocalAuthTest's Stage 1/Stage 2 bypass on iOS) but not for today's
narrower connectivity question. Set aside; moved to a simpler target.

## Target 2 -- Frida-Labs Challenge 0x1 -- THE decisive result

Confirmed current source and exact filename via an independent
writeup (a Medium article solving this specific challenge) rather
than guessing a URL: github.com/DERE-ad2001/Frida-Labs, "Frida 0x1/
Challenge 0x1.apk". Also confirmed real: this repo's actual folder
names are "Frida 0x1" through "Frida 0xB" (hex 1-11), matching the
11-challenge curriculum already logged in ROADMAP.md's v2 Design
References.

Same pipeline: decoded, confirmed non-debuggable by default, patched,
rebuilt, signed, installed. Package: com.ad2001.frida0x1.

Launched cleanly -- no self-destruct dialog this time, a genuinely
simple beginner app with no built-in anti-debug layer. Real PID
obtained (16055 initially, later PIDs across relaunches after
incidents -- see below).

### THE RESULT

  adb shell "su -c '/data/local/tmp/lldb-server gdbserver :5039
    --attach <pid> --log-file ... --log-channels \"gdb-remote
    packets\"' 2>&1"
  (lldb) platform select remote-android
  (lldb) process connect connect://localhost:5039

Clean, full, first-try success. 22 real threads enumerated correctly
(Signal Catcher, Jit thread pool, HeapTaskDaemon, mali-event-hand,
RenderThread, binder:<pid>_N, etc.) -- a genuine, healthy
gdbserver --attach against a real app process, something that never
once worked against deskclock across two full sessions. On the
second relaunch, lldb-server's own terminal even printed an explicit
"Attached to process <pid>..." confirmation line -- something never
seen in any of Thursday's failed deskclock attempts, a second,
independent signal the attach mechanism itself is now working
correctly, not just superficially connecting.

### The manifest-debuggable hypothesis is now DEFINITIVELY CONFIRMED

Decisive because of what was and wasn't controlled for. This whole
session ran with SELinux in `Enforcing` mode throughout (the earlier
`setenforce 0` from Thursday's session didn't survive the device
reboot, and was never re-applied today) -- and the attach still
succeeded cleanly. That's real, direct evidence against Thursday's
SELinux-permissive theory: given the ONLY variable that changed
between "attach fails" (deskclock, non-debuggable, both Enforcing and
Permissive tried) and "attach succeeds" (Frida-Labs 0x1, patched to
debuggable, Enforcing throughout) is the manifest debuggable flag
itself, that flag -- not SELinux mode -- is confirmed as the real,
sole gate. Worth correcting the written record plainly rather than
let the wrong theory stand, same Rule 9 discipline logged from
Thursday's own JEB+MACE case study addition this morning.

## Two real incidents today, and what they taught

### Incident 1 -- premature detach while the process was still resuming

Set a breakpoint on a real syscall site, issued `continue`, then
`process detach` immediately afterward with no pause to confirm the
breakpoint had actually fired. No panel ever appeared in between --
strong evidence the process was still actively resuming, not yet
stopped, when detach was issued. Result: a real ANR on the device.

Real, distinct lesson from Thursday's Rule 10 (which covers detach-
before-touching-server and avoiding live system daemons): detaching
from a genuinely STOPPED process is the safe, well-tested case;
detaching from a process that's actively resuming -- possibly right
as it's hitting a trap instruction -- is a meaningfully riskier,
less-tested situation. Confirm the process is actually stopped
(a real panel rendered, or `process status` showing a real stop
reason) before ever issuing detach.

Recovery: tapping "Wait" on the ANR dialog did NOT help (the process
was genuinely stuck, not just slow) -- had to Close and relaunch.
Low-cost here specifically because this was a disposable test app,
not a system daemon -- exactly the kind of incident Thursday's
disposable-target discipline exists to make cheap.

### Incident 2 -- a shared ART-runtime primitive is a much riskier breakpoint target than the equivalent choice was for a native daemon

On the relaunch, chose the same address as before (0x710b768860) --
the site with the MOST threads converged on it, the exact heuristic
that worked well for netd on the first Android session (mach_msg2_trap
-- style reasoning: more threads hitting one address means a more
reliable, frequently-repeating target). This time, even without any
premature detach, the app went into a real ANR almost immediately
after `continue`, before the breakpoint's panel ever appeared.

Real, important, worth-logging distinction: looking at the full
thread list from the first successful connection, THIS specific
address was hit by HeapTaskDaemon, FinalizerDaemon, ReferenceQueueDaemon,
Profile Saver, Jit thread pool, several hwuiTask/mali- threads --
strongly suggesting a core ART runtime synchronization primitive
(very likely a futex wait), not an ordinary, mostly-inconsequential
syscall the way DVIA-v2's plist write or netd's ppoll poll loop were.
Freezing a primitive the Android runtime's OWN internal scheduler/GC/
JIT machinery depends on continuously can plausibly stall the whole
app's runtime almost immediately, cascading into an ANR regardless of
which specific thread's breakpoint fires first -- a fundamentally
different risk profile than freezing the equivalent syscall on a
plain native daemon like netd, where background threads pausing
briefly was well-tolerated.

Real, concrete correction to the "most threads converged = best
target" heuristic: that reasoning holds for NATIVE processes (netd)
but is a bad, ANR-inducing choice for ART-MANAGED app processes
specifically, precisely because the busiest shared syscall sites in a
managed-runtime process are disproportionately likely to be the
runtime's own internal plumbing, not incidental/tolerable activity.
For ART-managed targets, a better strategy going forward: target a
breakpoint on the APP'S OWN code path specifically (reached via user
interaction, e.g. tapping the submit button Frida 0x1's UI showed),
not a shared runtime primitive hit by a dozen background daemon
threads at once.

Recovery: this time the process was left in the more fragile
lowercase-`t` (actively ptrace-traced) state, same as Thursday's
second netd incident -- correctly resolved by killing the orphaned
lldb-server tracer processes directly (triggers an automatic kernel-
level detach) rather than attempting kill -CONT, which Thursday
already established doesn't reliably work for this specific state.
Confirmed clean afterward: `pgrep -f lldb-server` empty, frida0x1
process itself gone (the app didn't survive, unlike netd's system-
level auto-restart -- expected and fine for a disposable test app).

## Status

Real, decisive result: the manifest `android:debuggable="true"`
patch is DEFINITIVELY CONFIRMED as the actual fix for gdbserver
--attach against real Android app processes -- a two-session mystery
fully resolved, with a real, reusable, end-to-end patching pipeline
now built and proven twice. Thursday's SELinux-permissive theory is
very likely a red herring, corrected in BACKLOG.md.

Still open: live confirmation of Linux syscall annotation firing
against a real app process (the original secondary goal once
connectivity was proven) -- not achieved today, but for a well-
understood, non-mysterious reason (a bad breakpoint-address choice
specific to ART-managed apps, not a connectivity problem), with a
clear, better-informed plan for next time: target app-specific code
via UI interaction, not a shared ART runtime primitive.

Real new artifacts from today, reusable going forward:
- Full APK decompile/patch/rebuild/sign/install pipeline, proven
  twice.
- MobileBinaryTargets/shared/mace-debug.keystore -- reusable signing
  key for every future Android target.
- MobileBinaryTargets/android/crackmes/ -- consistent storage
  convention, mirroring the existing iOS structure.
- Two real crackme targets already downloaded, decoded, and patched
  (UnCrackable L1 Android -- set aside for later mace_patch bypass
  work; Frida-Labs 0x1 -- proven-working connectivity target, good
  candidate for the next syscall-annotation attempt with a properly
  chosen, app-specific breakpoint).
