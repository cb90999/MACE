## Status and purpose

This is deliberately PROVISIONAL, not a permanent artifact. Every
lesson here comes from real, hard-won mistakes made this project —
including by an LLM (Claude) acting as the analyst's assistant, the
same role a v3 agent will play. The honest, ideal long-term home for
this content isn't a hand-maintained markdown file at all — it's
baked directly into v3's own MCP tool responses: a `mace_set_breakpoint`-
style tool that gets no hit after several continues should itself
return a structured hint ("no hit after 3x continue — is this a
one-shot call? has the containing code path actually executed? check
thread list before assuming failure"), the same principle already
logged as the v3 tool-legibility lesson (ROADMAP.md, 2026-08-29) — an
agent's guidance should come from the tool's own source and behavior,
not separate prose that can silently drift from what the code
actually does.

Until that exists, this file is the interim scaffolding: rules an
agent (or a human) should apply when debugging with MACE, each one
tied to a real incident where NOT following it cost real time. Format
is deliberately "if you see X, don't assume Y, do Z" — a runbook to
consult mid-session, not a retrospective to read once.

## Verify, don't assume — the one rule underneath all the others

Every specific lesson below is really an instance of this. lldb's own
REPL doesn't block and wait for a stop to actually complete before
showing the next prompt — commands sent in a rapid burst can land
while the process is still mid-flight, silently producing wrong
results rather than an error. A command "succeeding" (a breakpoint
resolving, a search returning zero matches, a process reaching a
healthy-looking state) is never sufficient evidence on its own — check
`process status`, `br list`, `thread list`, or a known-good control
query before drawing a conclusion from it.

## Rule 1 — a resolved breakpoint is not a confirmed-working breakpoint

**Symptom:** `br set` reports a real symbol name and address, but the
breakpoint never fires despite the code path genuinely running.

**Don't assume:** the breakpoint mechanism itself is broken, or that
shared-cache library addresses are unreliable in general.

**Do instead:** check `br list` for `hit count`. If it's still 0 after
the code should have run, check `process status` and `thread list` —
the containing code path may simply not have executed on this run
(see Rule 2), or the specific call site may be one-shot rather than
repeating (see Rule 3). Only treat the breakpoint mechanism itself as
suspect if a DIFFERENT, frequently-repeating call at the same
scope/module also fails to fire under the same conditions.

**Real incident:** a whole session was spent concluding "shared-cache
breakpoints are unreliable" after four separate libsystem_kernel.dylib
symbols failed to fire (__ptrace, __open and three siblings, plus a
hardware breakpoint against UnCrackable L2). That conclusion was WRONG
— disproven the same session when a breakpoint on mach_msg2_trap
(same shared-cache image) fired immediately, first attempt. The real,
correct explanation: every earlier failure was either a genuinely
one-shot call, or a code path confirmed absent via thread list — not
shared-cache placement, which is demonstrably fine.

## Rule 2 — check thread list before concluding a code path never executed

**Symptom:** a backtrace on the current/default thread shows a
healthy, unremarkable state, and you're tempted to conclude "nothing
unusual happened here."

**Don't assume:** the default thread's backtrace tells the whole
story. A stop-hook panel renders per-thread; a genuinely new thread
(spawned mid-session, or one your target function was supposed to
create) is easy to miss entirely if you only ever check thread #1.

**Do instead:** run `thread list` explicitly whenever you need to
confirm whether a specific piece of code executed (e.g. "did this
function spawn a background thread") rather than inferring it from
the main thread's state alone.

**Real incident:** UnCrackable L2's viewDidLoad is documented to spawn
a background thread via detachNewThreadSelector. The main thread's
backtrace looked completely healthy (a normal CFRunLoopRun) —
`thread list` was what actually revealed only 3 threads existed, none
of them the expected new one, proving the whole post-ptrace tail of
viewDidLoad had been skipped when launched via debugserver-by-path.

## Rule 3 — one-shot calls are fundamentally harder to catch than repeating ones, and that's often the real variable

**Symptom:** a breakpoint on a real, correctly-resolved instruction
never fires, and the target's own documentation or a reference writeup
confirms the code genuinely executes under normal conditions.

**Don't assume:** the breakpoint targeting logic, the tool, or your
understanding of the target is wrong.

**Do instead:** ask whether the specific call is one-shot (executes
once, early, and is easy to race past) versus repeating (executes on
every run-loop cycle, every file open, etc.). For a one-shot call,
consider launching fresh with the breakpoint armed BEFORE the first
`continue` (see Rule 5), or finding a repeating call in the same
region to validate the mechanism first before trusting a one-shot
miss as meaningful.

**Real incident:** the same session as Rule 1 — mach_msg2_trap (fires
on essentially every run-loop iteration) caught cleanly on the first
attempt, while __ptrace (called once, early, during app startup) and
a single ordinary open() call both missed repeatedly under
superficially identical conditions.

## Rule 4 — module-scoped symbol search can silently fail; verify with a known-good control query first

**Symptom:** `image lookup -rn "<pattern>" <module>` returns empty for
a term you're fairly confident should exist.

**Don't assume:** the term genuinely doesn't exist in that module.

**Do instead:** run the identical search for something that MUST
exist in any compiled binary — `image lookup -rn "main" <module>` — as
a control. If even that comes back empty, the module-scoped search
itself is unreliable for this specific module (root cause not fully
understood as of 2026-08-30 — see BACKLOG.md), and you should fall
back to `image dump symtab <module>` (optionally filtered through
mace_grep) or `strings` on the actual binary instead of continuing to
trust `image lookup`'s module-scoped form.

**Real incident:** iGoat-Swift's own class/method symbols returned
empty for every search tried, including "main" — the control query
that proved this wasn't a real absence, but an unreliable search path
for that specific module. `image dump symtab` (9475 real entries) and
eventually `strings` on the extracted binary gave the real, ground-
truth answer.

## Rule 5 — launching fresh vs. attaching to an already-running process are genuinely different regimes; don't assume lessons from one transfer to the other

**Symptom:** you need to catch something that happens very early in a
process's life (before you could realistically attach in time).

**Don't assume:** launching directly via `debugserver <path>` behaves
like attaching to an already-running process, just earlier.

**Do instead:** treat launch-by-path as its own regime that needs
separate validation. Set breakpoints by NAME (so lldb can resolve them
lazily as libraries load) rather than by address computed before the
process has even reached `_dyld_start`. Verify the process reaches a
genuinely healthy state (thread list, backtrace) before trusting that
a code region you expected to run actually did.

**Real incident:** this project's first-ever launch-by-path attempt
(UnCrackable L2) produced a real, still-not-fully-explained anomaly —
an entire code region (viewDidLoad's post-ptrace tail) appears to get
skipped specifically under this launch mode, never observed under
the normal attach-to-already-running workflow used successfully every
other time this project.

## Rule 6 — a tool's own "no matches" result deserves the same skepticism as a target's

**Symptom:** a MACE-native tool (mace_grep, mace_search) returns
"no matches" for a pattern you're confident should be present.

**Don't assume:** the underlying question has a negative answer.

**Do instead:** check whether the pattern itself needed quoting or
escaping — as of 2026-08-30, mace_grep does not strip surrounding
quotes from its PATTERN argument (only from the inner command), so a
pattern like `"a|b|c"` can silently corrupt matching on the first/last
alternatives. Prefer patterns with no spaces or special characters
where possible; if a real match is suspected despite an empty result,
retry with the quotes/escaping removed before concluding the search
was accurate.

**Real incident:** this exact bug produced misleadingly narrow ("1 of
770 lines") results twice in one session, on two different searches,
before being correctly diagnosed.

## Rule 7 — daemon-mediated operations never touch the app's own process

**Symptom:** a confirmed, real user-visible action (e.g. "Data saved")
happens, but no syscall breakpoint in the app's own process fires for
it.

**Don't assume:** the breakpoint or the mechanism is broken.

**Do instead:** consider whether the operation is actually handled by
a separate system daemon over IPC/XPC rather than by the app process
itself. Keychain operations (SecItemAdd, SecItemCopyMatching) are the
clearest example — they're Mach IPC calls to securityd, a completely
separate process; the app never calls open() on the keychain database
itself. Prefer operations known to be synchronous and in-process
(e.g. NSDictionary.write(toFile:atomically:) for a plist) when the
goal is specifically to catch a real syscall in the TARGET app's own
process.

## Rule 8 — a "no GUI" or otherwise-quiet result is not automatically a failure signal

**Symptom:** an app is launched or interacted with and nothing visible
happens.

**Don't assume:** the process crashed, hung, or failed to launch.

**Do instead:** check `process status`, interrupt and get a real
backtrace, or check whether the app is simply not the frontmost/
visible one (e.g. needs SpringBoard's own app-switcher gesture to
actually display, even though the process itself is healthy and
running normally). A quiet result is genuinely ambiguous between
several very different explanations — resolve it with direct
evidence, not assumption, before acting on it either way.

## Rule 9 — hold a theory loosely, and be willing to retract it publicly the same session

Not a symptom/fix pair like the rules above — a standing practice.
When a pattern across several failures suggests an explanation (e.g.
"shared-cache breakpoints don't work here"), keep testing rather than
settling once the explanation feels sufficient. If new evidence
contradicts it — even evidence gathered five minutes after floating
the theory — say so plainly and correct the written record, rather
than letting a plausible-sounding but wrong conclusion stand
undisturbed. Rule 1's real incident is the clearest example of this
in practice.

A real, independent confirmation this pattern holds outside this
project too, worth remembering: a credentialed external researcher
(yuvalino, research log 2026-09-08, see ROADMAP.md's Rationale
section) hit a deterministic crash, initially assumed his own code
must be wrong, tried to explain it away with corruption theories —
and only cracked the real cause once he stopped defending "it must be
my code" and escalated to reading the actual kernel source. Same
underlying discipline as this rule: don't let a comfortable
explanation substitute for checking the layer below it.

## Rule 10 — never attach to a live system daemon; always detach cleanly before touching the server terminal

**Symptom:** debugging a system-critical process (a network daemon, a
service manager, anything other processes actively depend on) causes
visible, real side effects — an "App Not Responding" dialog, a crash,
degraded device behavior — during or after a debugging session.

**Don't assume:** stopping a debug session cleanly on the client side
(quitting lldb, Ctrl+C on the server) is sufficient to guarantee the
target resumes normally. Killing a debugger/tracer abruptly can leave
the target's threads stopped (job-control state, recoverable with
`kill -CONT <pid>`) or, worse, in an active ptrace-trace state
(lowercase `t` in `ps`, more fragile — killing the orphaned tracer
process is the correct fix here, since a dying tracer triggers an
automatic kernel-level detach, but the target can still crash rather
than cleanly resume).

**Do instead:** two separate disciplines, both real:
1. Always issue `process detach` from the debugger CLIENT before
   touching the server process at all — detach first, then stop the
   server, never the reverse order.
2. Never choose a live system-critical daemon as an iterative
   debugging target in the first place, especially early in learning
   a new platform's connection quirks. Use disposable, purpose-built
   test targets (a dedicated test app, a crackme) where an unclean
   stop costs nothing beyond relaunching that one process. This isn't
   a workaround for a MACE limitation — it's the same discipline every
   iOS target this project used from the start (LocalAuthTest,
   DVIA-v2, iGoat, UnCrackable — never a real system process).

**Real incident:** the first Android connection session (2026-09-06)
attached to netd (a live network daemon) to validate multithreaded
panel rendering. An improper Ctrl+C-based stop left its threads frozen
long enough to trigger a real "App Not Responding" dialog (recovered
via kill -CONT). A second incident during the same session left
threads in the more fragile ptrace-trace state; killing the orphaned
tracer processes correctly triggered a kernel-level detach, but netd
crashed rather than resuming — recovered only because Android's init
automatically relaunched it under a fresh PID within seconds. Real,
if costly, confirmation that the already-planned "disposable targets
only" discipline was correct from the start.

## Rule 11 — confirm the process is genuinely stopped before detaching, not just resumed

**Symptom:** issuing `continue` followed immediately by `process
detach`, with no pause in between to confirm a breakpoint actually
fired, causes a real ANR or otherwise leaves the target in a bad
state.

**Don't assume:** detaching from a debugger session is uniformly safe
regardless of the target's current state. Detaching from a process
that's genuinely STOPPED (a real panel rendered, `process status`
shows a real stop reason) is the safe, well-tested case. Detaching
from a process that's actively RESUMING — possibly right as it's
hitting a trap instruction — is a meaningfully riskier, less-tested
situation: the debugger that would normally resolve the trap has just
left, potentially leaving an unhandled signal mid-flight.

**Do instead:** after `continue`, wait and actually confirm a stop
happened (the panel rendered, or an explicit `process status` check)
before issuing `process detach`. Don't chain continue and detach back
to back on the assumption the breakpoint fired instantly.

**Real incident:** the second Android connection session (2026-09-11)
chained `continue` then `process detach` immediately, with no panel
ever appearing in between. The target app went into a real ANR
immediately afterward — strong evidence the process was still
actively resuming, not yet stopped, when detach was issued.

## Rule 12 — on ART-managed app processes specifically, avoid breakpoints on shared runtime-synchronization primitives

**Symptom:** a breakpoint chosen because many threads independently
converge on the same address — a heuristic that worked well on a
native process — causes an immediate ANR on an ART-managed (Java/
Kotlin) Android app process, even with no premature detach involved.

**Don't assume:** "most threads converged on this address" is a
platform-independent proxy for "reliable, low-risk target." On a
native process (a plain daemon with no managed runtime), a busy
shared syscall site is usually just incidental, tolerable activity —
freezing it briefly costs little. On an ART-managed app process, the
busiest shared syscall sites are disproportionately likely to be the
runtime's OWN internal synchronization primitives (very likely futex
waits) that ART's own scheduler, garbage collector, and JIT
continuously depend on — freezing one can stall the whole app's
runtime almost immediately, a fundamentally different risk profile.

**Do instead:** on ART-managed app targets specifically, prefer a
breakpoint on the APP'S OWN code path — reached via real UI
interaction (e.g. tapping a button the app's own activity handles) —
over a shared syscall site with many background daemon threads
converged on it. Treat "most threads = most reliable target" as a
native-process-specific heuristic, not a general rule.

**Real incident:** the second Android connection session (2026-09-11)
reused the exact "most threads converged" heuristic that worked
cleanly for netd (a native daemon) on the first Android session,
applying it to an ART-managed app process (Frida-Labs Challenge 0x1).
The chosen address was hit by HeapTaskDaemon, FinalizerDaemon,
ReferenceQueueDaemon, Profile Saver, Jit thread pool, and several
hwuiTask/mali- threads — a strong signature of a core ART runtime
primitive, not incidental activity. The app went into a real ANR
almost immediately after continue.

## Rule 13 — on Android, explicitly configure SIGCHLD not to stop the process, before doing anything else

**Symptom:** continuing past a breakpoint (even one that never
resolved to a real location) leads to a stop specifically for
`SIGCHLD`, followed immediately by a real ANR — with no clear
connection to anything the session was actually trying to do.

**Don't assume:** `lldb`'s default signal-handling behavior is
appropriate for every target. `SIGCHLD` is a routine, frequent signal
— sent whenever any child process changes state — and is essentially
constant background noise in Android's Zygote-based app model.
Stopping the entire process every time it fires is disruptive and
serves no debugging purpose on Android, the same reasoning already
behind iOS's own default `unix-signals` list excluding routine
signals from causing stops.

**Do instead:** as a standard first step for every Android session,
not just when troubleshooting:

  (lldb) process handle SIGCHLD -n false -p true -s false

(don't notify, do pass through to the app normally, don't stop on
it). Worth checking whether other routine signals need the same
treatment as more Android sessions accumulate.

**Real incident:** the second manifest-patch session (2026-09-12)
hit a stop specifically labeled "thread 2 received signal: SIGCHLD"
immediately before a real ANR, while investigating an unrelated
module-resolution problem. Applying this signal handling did not by
itself resolve the module-resolution issue, but is a real, independent
fix worth keeping regardless.

## Rule 14 — repeated attach+continue cycles on a real ART app process carry a real, distinct crash risk, separate from the ANR risk in Rule 12

**Symptom:** continuing past a correctly-set breakpoint doesn't hit
the intended target — instead, an unrelated background thread crashes
with a real signal (e.g. SIGSEGV), often a different thread each time,
sometimes with an identical instruction-level signature across
attempts.

**Don't assume:** this is the same ANR risk already covered by Rule
12. Rule 12 is about choosing a bad breakpoint TARGET (a shared
runtime primitive) that freezes the whole app. This is different: a
real crash in a thread completely unrelated to the chosen breakpoint,
that appears to be a side effect of the repeated attach/continue cycle
itself on a busy, multi-threaded ART process — root cause not
understood as of this writing.

**Do instead:** treat repeated attach+continue cycles against a real,
already-running ART app process as carrying real, not-fully-understood
risk, distinct from and in addition to careful breakpoint-target
selection. Recover the same way as any other fragile-state incident
(check `ps -T`, kill the orphaned tracer directly if threads show
lowercase `t`) — this doesn't require a different recovery procedure,
just recognition that it's a different failure mode worth documenting
separately rather than conflating with Rule 12's ANR risk.

**Real incident:** 2026-09-13, testing a correctly-computed address
breakpoint against a real EEA validation app. Continuing past the
breakpoint twice, on separate attempts, produced an unrelated SIGSEGV
in a different background thread each time (SurfaceSyncGroup, then
AsyncTask #1) — both with the identical instruction signature
(`ldr x21, [x21]`, fault address 0x0) and an identical trailing
instruction sequence, strongly suggesting the same underlying cause
each time, not coincidental unrelated crashes.

**UPDATE, same day, later session:** root cause is now understood,
not just documented as unknown. An independent troubleshooting
document named this directly and it was confirmed live: ART's JIT
compiler generates routine SIGSEGVs as part of a normal null-check-
elimination technique — not real crashes at all, and not specific to
this project's setup. Fix is the same shape as the SIGCHLD handling
above:

  (lldb) process handle -s false -n false -p true SIGSEGV

Apply this alongside SIGCHLD handling as standard practice on every
Android session, not just when troubleshooting. Confirmed: no
SIGSEGV-related stop occurred after applying this, on a session that
had shown the crash pattern reliably before.

## Rule 15 — when debugging a new platform's connection model, ask who actually performs the attach

Not a symptom/fix pair like the rules above — a standing practice,
the same shape as Rule 9.

When comparing two platforms' working connection recipes (or
debugging why one platform's recipe doesn't transfer to another),
don't just compare the literal command sequences side by side. The
more useful question is: which side — the on-device server, or the
debugger client's platform plugin — actually performs the process
attach. That single distinction explains far more than the commands
themselves do.

**Real example this project has now confirmed:** on iOS, `debugserver
--attach=<PID>` does the attaching itself, in its own launch command;
lldb's `process connect` just joins an already-established session.
On Android's actual working recipe, `lldb-server platform` mode opens
a listening/discovery layer only — attach happens as a SEPARATE,
later step (`process attach --pid <PID>`), performed by lldb's own
remote-android platform plugin client-side, not by the on-device
server at all.

**Why this matters, not just as trivia:** the platform that needs the
richer, client-side attach logic is the one with the more complex
process model to reconstruct. Android's Zygote-forked, ART-managed,
JNI-heavy process model needs lldb's own platform plugin actively
doing that reconstruction work — a bare "connect to whatever's
already attached" was never going to be enough. iOS's simpler,
single-Mach-O-binary-per-process model doesn't need that extra layer;
a plain server-side attach already hands lldb a complete picture.

**Apply this before assuming a working recipe from one platform will
transfer to another, or before concluding a whole connection mode
(like `platform` mode) is "wrong" based on one failed attempt** — the
2026-09-08 to -13 "platform mode is confirmed the wrong choice"
mistake (see BACKLOG.md's SUPERSEDED entry) this distinction wasn't asked about early enoughhappened partly because
this distinction wasn't asked about early enough.

## Rule 16 — re-read the primary source before reproducing a recipe from memory, don't transcribe it from summary

**Symptom:** a previously-verified recipe fails at a step that the
original source document actually covered, because the step was
silently dropped or altered when the recipe was recalled from memory
or from a summarized account of the original session rather than the
source document itself.

**Don't assume:** a recipe you've already seen work once is safe to
reproduce from memory. A summary compresses detail, and a small,
easy-to-miss detail (a flag, a privilege level, an ordering
requirement) can be exactly the part that made the original attempt
work.

**Do instead:** before reproducing a previously-verified multi-step
recipe, re-read the actual primary source document (not a summary of
it) and follow it literally, then adapt only if a real, understood
reason requires a change.

**Real incident:** 2026-09-17's first EEA reproduction attempt started
`lldb-server platform` without `su -c`, even though
android_platform_mode_resolution_notes.md's own verified command
sequence used `adb shell su -c '...'` throughout. The omission wasn't
a new discovery — it was a transcription error from reconstructing
the recipe from memory rather than re-reading the notes file first.
`platform connect` still succeeded (that layer doesn't need root),
masking the problem until `process attach` failed with "lost
connection".

## Rule 17 — kill stale `lldb-server` processes before every fresh Android session, not just during incident recovery

**Symptom:** a new `lldb-server platform` session behaves
inconsistently (unexplained connection drops, attach failures) even
though the commands themselves match a previously-verified recipe
exactly.

**Don't assume:** a fresh `adb shell su -c 'lldb-server platform ...'`
invocation starts from a clean slate. Each failed or abandoned attempt
can leave its own listener and/or orphaned child process behind on the
device; these accumulate silently across retries within the same
session.

**Do instead:** before starting `lldb-server` for a new attempt, always
check for and clear existing instances:

    adb shell ps -A | grep lldb-server
    adb shell su -c 'kill -9 <all listed PIDs>'
    adb shell ps -A | grep lldb-server   # confirm empty

Treat this as routine session-start hygiene, the same standing
practice as Rule 13/14's signal handling — not something to reach for
only after something has already gone wrong.

**Real incident:** 2026-09-17 — by the third `lldb-server` restart
attempt in one session, `ps -A | grep lldb-server` showed four
resident processes: two live listeners, an orphaned zombie child from
an earlier failed attach, and one active child from a later attempt.
A real, credible contributor to that session's connection instability,
only found by explicitly checking rather than assuming.

## Rule 18 — a breakpoint on a main-thread call site will trigger Android's ANR dialog; this is expected, not a failure

**Symptom:** continuing past a breakpoint set on code that runs
synchronously on an app's main/UI thread (e.g. a native function
called directly from a button's click handler via JNI) produces a
real "isn't responding" ANR dialog on-device.

**Don't assume:** the ANR means the process crashed, hung, or that the
breakpoint mechanism is broken. Android's watchdog surfaces this
dialog precisely because the main thread is, correctly, not
responding — it's genuinely paused at the breakpoint, which is exactly
what was asked for.

**Do instead:** tap **Wait**, never "Close app" — this keeps the
process alive. If in doubt whether the thread is merely paused versus
actually stuck, `process interrupt` followed by `thread list` will
show a clean, recognizable idle/parked state (or the breakpoint
address itself) rather than anything resembling corruption. Continue
normally once inspection is done; the dialog clears on its own once
the thread responds again.

**Real incident:** 2026-09-17, breakpointing `validate()` in the EEA
app (called synchronously from `Java_..._checkInput`, itself wired
directly to the Submit button) produced this ANR dialog on both
reproduction attempts. `process interrupt` + `thread list` during one
such dialog showed thread #1 cleanly parked in `__epoll_pwait` (normal
idle wait) — confirming the process was healthy, not hung — and the
breakpoint fired correctly on the very next `continue`.

## Rule 19 — a connection dropped without a clean detach can leave every thread job-control-stopped; `kill -CONT` recovers it, same as Rule 10's less-severe case

**Symptom:** the lldb client reports `Process <pid> exited with status
= -1 (0xffffffff) lost connection`, and the on-device app becomes
genuinely, repeatedly unresponsive afterward (ANR recurring even after
tapping Wait), rather than merely showing a stale dialog.

**Don't assume:** the app process itself crashed or needs to be force-
stopped and relaunched. A debugger connection dying mid-session
(rather than via a clean `process detach`) can leave every thread
exactly where it was when the tracer disappeared — genuinely stopped,
not corrupted.

**Do instead:** check thread state directly before assuming the
process is lost:

    adb shell ps -T -p <pid>

Uppercase `T` across all threads is Rule 10's less-severe, recoverable
case:

    adb shell su -c 'kill -CONT <pid>'

(Lowercase `t` is the more fragile ptrace-trace case Rule 10 already
covers — killing the orphaned tracer process is the fix there
instead.)

**Real incident:** 2026-09-17, continuing past a new, previously-
unseen `fork` stop reason dropped the platform-mode connection
outright. `ps -T` showed all ~40 threads in uppercase `T` state;
`kill -CONT <pid>` un-froze the app immediately, which then ran
`validate()` to completion on its own and displayed its normal result
-- full recovery, no relaunch needed. Root cause of the connection
drop itself (why resuming past a fork event kills the session) remains
unexplained -- flagged honestly as a distinct open question from the
already-documented SIGCHLD/SIGSEGV signal-handling gaps.

## Rule 20 — Full Text

"**Symptom:** a binary's behavior seems to depend on some prior condition
(instrumentation present, a prior check passed, a mode flag) but nothing
in the immediately-visible logic explains how that condition is being
tracked.

**Don't assume:** the condition is checked and acted on in the same place,
or that you need to trace the check's own logic to find where it's used.
Look instead for where its result is *stored* -- a register written
immediately after a call/dispatch returns, then read by a conditional
branch shortly after, is very likely that stored condition, however
unrelated the surrounding code looks.

**Do instead:** `reg read` the suspect register right at the branch that
consumes it. If it's a genuine boolean gate, this confirms it in one
command, and the register becomes a live-patchable target
(`mace_patch reg write` to either polarity) rather than something you'd
need to reverse-engineer analytically.

**Real incident:** 2026-09-24, enigma_v2 CTF (self-authored). `svc #0x15`
dispatches to `is_frida_active()`, whose return is stored in `x28`, then
consumed several lines later by `cbz x28, frida_clean` -- if Frida is
detected, the corruption path silently XORs noise into both accumulators
each iteration instead of failing outright. `reg read x28` at that `cbz`
confirms the gate in one step. Generalizes directly from the already-
proven MACELocalAuthTest bypass (2026-08-21): both are single-boolean-
register-gates-behavior shapes -- LocalAuth needed force-true to fake
success, this gate's theoretical bypass is the mirror-image force-false
(`mace_patch reg write x28 0` right after the svc #0x15 return) had Frida
actually been detected. Supersedes an earlier, wrong version of this same
observation from 2026-09-17 research conversation, which assumed the
mechanism was 'a register zeroed before a gating branch forces bypass' --
right instinct, wrong specific register and wrong specific mechanism until
checked against the real source.

## Rule 21 — Full Text

"**Symptom:** a conditional branch leads to a plausible-looking alternate
code path -- another apparent check, another apparent algorithm variant --
sitting right next to the real logic, and static/LLM analysis treats it as
a real candidate.

**Don't assume:** a branch target is reachable just because the
surrounding code looks like ordinary control flow. Some branches are
opaque predicates: the condition they test is provably constant by simple
math (x XOR x, x * 0, n*(n+1) parity), making the branch statically dead,
but deliberately built to look like a live decision point to mislead a
reader who doesn't verify the condition's actual value.

**Do instead:** `reg read` the condition register at the branch itself,
every time, regardless of how confident the arithmetic identity seems from
reading the disassembly. Confirming a predicate is always-constant this
way takes one command; proving the same thing by symbolic/SMT reasoning
(see r2SMT in this backlog) is real work by comparison, and getting it
wrong sends analysis down a fabricated path.

**Real incident:** 2026-09-24, enigma_v2 CTF. Three separate opaque
predicates (`tst x9,#0x1` off `mul x9,x9,x21` where x9=char*(char+1),
always even; `cbnz x9,fake_eea` off `eor x9,x22,x22`, always 0;
`cbnz x9,fake_check` off `mul x9,x25,xzr`, always 0) each gate a decoy
branch built to look like a real check. A tested LLM analyzing this
binary walked directly into `fake_check`'s `cmp x20, #0x7F` as the real
validation, spending 3+ hours before giving up, entirely because it never
confirmed the gating register's live value at any of the three branches.

## Rule 22 — Full Text

"**Symptom:** a disassembly shows `svc` instructions with immediate values
that don't correspond to any real syscall number for the target platform,
or a syscall-table lookup returns nothing or something implausible for
them.

**Don't assume:** the annotation feature has a gap, or the immediate is
simply unrecognized/unusual. Check first whether the binary has installed
its own `SIGSYS` handler (commonly via `sigaction` inside a
`__attribute__((constructor))` function, itself worth flagging on sight) --
if so, every `svc` in that process may be an app-defined dispatch
mechanism riding on the same trap instruction as a real syscall, not a
syscall at all.

**Do instead:** locate the SIGSYS handler and read how it decodes the
triggering instruction (typically extracting the immediate from the raw
instruction bytes at `pc-4`) and what it dispatches to -- an internal
function table, not the kernel. Annotate accordingly: label these
explicitly as custom dispatch, don't force a real-syscall-table name onto
them.

**Real incident:** 2026-09-24, enigma_v2 CTF. `svc #0x10` through `#0x15`
are entirely custom -- a constructor-installed SIGSYS handler decodes the
svc immediate from `*(uint32_t*)(pc-4)`, indexes a local
`dispatch_table[]`, and calls ordinary C functions (`get_magic1`,
`get_prime`, `access_granted`, `access_denied`, `get_magic2`,
`is_frida_active`), writing the return into the saved context's `x0`.
Direct, concrete instance of the adversarial case the v2.5 rationale
predicted ('a stripped, syscalls-only binary is close to an ideal stress
test for the syscall annotation feature') -- this binary is that test
case. Distinct from the already-logged fatalsec/renef raw-SVC research
above: that thread is about hiding real syscalls from libc; this is about
hijacking the trap mechanism for an unrelated purpose entirely. Also
responsible, via the same `volatile`-arithmetic constant-hiding technique
in `get_prime()`/`get_magic1()`/`get_magic2()`, for the tested LLM's
`x24=argc` misread -- no static value ever appeared as an immediate to
anchor to."

## Rule 23 — Full Text

"**Symptom:** a native breakpoint deliberately blocks an app's main thread
(e.g., inside a JNI-exported function), and you expect Android's ~5-second
`inputDispatchingTimeout` to eventually surface an ANR dialog. It never
does -- the UI sits frozen for minutes with no dialog, however long the
breakpoint is held.

**Don't assume:** the currently-attached debugger session is what's
suppressing the ANR, or that removing it restores normal behavior.
Detaching JDWP (`jdb`), clearing `am clear-debug-app`, and even fully
`lldb detach`-ing (confirmed via `TracerPid: 0` in `/proc/<pid>/status` --
zero debuggers attached by any means) does not bring ANR back for that
same process. A plain `kill -STOP <pid>` on the same PID, no debugger
involved at all, still produces no ANR.

**Do instead:** recognize the exemption is tied to the process instance,
not to an active debugger connection. Once a PID has been associated with
a debugger at any point since it spawned, AOSP's `ActivityManagerService` /
`ProcessErrorStateRecord` marks that process as debug-exempt from ANR for
the rest of its life, even after every debugger disconnects. To get a real
ANR baseline, or to test ANR-related behavior at all, `am force-stop` the
app and relaunch it fresh -- a new PID never touched by `-w`, `jdb`, or any
attach -- before the ANR mechanism will fire normally again.

**Real incident:** 2026-09-24, Frida-Labs Challenge 0x8
(`com.ad2001.frida0x8`). A native breakpoint on
`Java_com_ad2001_frida0x8_MainActivity_cmpstr` was held for 7+ minutes with
JDWP attached (no ANR), then 1+ minute with JDWP removed but lldb still
ptrace-attached (no ANR), then 2+ minutes with lldb also detached and the
process frozen via plain `kill -STOP` with `TracerPid: 0` confirmed (still
no ANR) -- all against the same PID (13033), which had been JDWP-attached
once at the very start of the session. Force-stopping and relaunching
produced a fresh PID (15339) never touched by any debugger; freezing that
one with the identical `kill -STOP` produced the standard "Frida 0x8 isn't
responding" ANR dialog within the normal timeout window. Practically
useful for MACE workflows: attaching once effectively grants a long-lived
ANR-free debugging window on that process -- but any ANR-timing experiment
must use a virgin process, not one reused across test iterations."

## Rule 24 — Full Text

"**Symptom:** the first `process attach` to an Android process on a given
device/OS build (or after clearing `~/.lldb/module_cache`) either appears
to hang indefinitely at "Manually indexing DWARF," or crashes lldb outright
with a segfault whose stack trace runs through
`AdbClient::SyncService::SendSyncRequest`.

**Don't assume:** `target.preload-symbols false` is a fix, even if setting
it before a retry appears to resolve the hang. It governs DWARF-indexing
eagerness, a step that happens after a module file is already fetched --
it has no effect on the module-fetch path itself, and a retry "working"
after setting it is very likely just riding on partial cache-warming left
over from the earlier interrupted attempt, not the setting doing anything.

**Do instead:** disable `target.parallel-module-load` instead. lldb's
Android platform plugin fetches uncached modules concurrently across a
thread pool (`DynamicLoaderPOSIXDYLD::LoadAllCurrentModules` dispatched via
`llvm::StdThreadPool`), and `AdbClient::SyncService`'s single connection
is not safe for concurrent use from multiple threads -- hitting it
concurrently races, and depending on scheduling either hangs or segfaults.
Setting `settings set target.parallel-module-load false` forces sequential
fetch instead: slower on a cold cache (expect several seconds to a minute
or more for 100+ modules, correctly, for a real reason this time) but
reliable. In practice this should be set proactively before any first
attach to a new device/OS build, not reactively after a hang.

**Real incident:** 2026-09-24/25, Frida-Labs Challenge 0x8
(`com.ad2001.frida0x8`). First attach (cold cache, default settings)
appeared to hang at DWARF indexing; a second attempt with
`preload-symbols false` set completed, and was provisionally credited as
the fix. The next day, a deliberately cleared cache reproduced a crash
(not a hang) inside `AdbClient::SyncService::SendSyncRequest` twice in a
row under default settings, and a third time even with
`preload-symbols false` set -- fully disproving it. Setting
`target.parallel-module-load false` on a fourth, equally cold cache
attempt completed cleanly in ~8 seconds with all 23 threads enumerated,
no crash. Corrects an unwritten, provisional conclusion from the prior
session before it became a documented rule -- caught by testing the fix
in isolation rather than trusting that a retry succeeding meant the
applied setting was responsible."
