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
