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
mistake (see BACKLOG.md's SUPERSEDED entry) happened partly because
this distinction wasn't asked about early enough.
