## Goal for the day (per ROADMAP.md)

Syscall annotation (svc #0x80 + x16) — the last unbuilt v1 feature.
iGoat was the originally-named target; today started there, pivoted
twice, and ended with the feature genuinely built and validated live.
Full arc below, including a theory that turned out wrong and is
corrected rather than left standing.

## Stage 1 — iGoat Tampering: same file as yesterday's Method Swizzling

Set up Tampering, expecting new content. Cloned the real
OWASP/iGoat-Swift source (git clone, not web scraping — sidesteps
GitHub's robots.txt block on /tree/ paths that blocked a plain
web_fetch attempt) and confirmed decisively: Tampering and Method
Swizzling are the literal same file
(Source/Exercises/Tampering/MethodSwizzlingExerciseVC.swift) — same
class, same Cydia/bash/apt/sshd path check already validated
2026-08-27. Checked Binary Patching too (simple password-reversal
challenge, no anti-debug at all, per its own source).

Then went further and searched the ENTIRE iGoat-Swift source tree:

  grep -rniE "ptrace|sysctl|P_TRACED|getppid|fork\(\)" --include="*.swift" .

Zero matches anywhere. Decisive, source-level confirmation (not just
binary guessing): iGoat-Swift contains no syscall-level anti-debug
technique anywhere in the app, in any challenge. iGoat was the wrong
TARGET, not just the wrong challenge.

## Stage 2 — MASTG UnCrackable Level 2: real anti-debug, hard-won

ROADMAP.md's own Priority 2 section already named UnCrackable L2
("ptrace loop") as the deferred, real anti-debug target — deliberately
held back until Priority 1 features were validated on cooperative
targets. CB proposed a middle path: use L2 only to catch the real
ptrace call for syscall-annotation validation, without taking on the
actual bypass problem Priority 2 defers. Agreed — real-world content
over a synthetic test, consistent with target-independence discipline
("the more real world scenarios we try, the better; synthetic
scenarios could lead to overfitting" — CB, 2026-08-30).

Downloaded from github.com/OWASP/mastg (current canonical home; this
project has moved through owasp-mastg -> mastg -> mas-crackmes over
the years). Real, independently-documented anti-debug content
confirmed before even starting: OWASP's own issue #1634 says "iOS
crackme level 2, is a simple crackme with anti debugging checks" and
flags "one of these checks is not working correctly" as a known,
pre-existing bug in the app itself.

### The mystery: correctly-placed breakpoints that never fired

Found the exact ptrace(PT_DENY_ATTACH) call site via a 2021 writeup's
byte-identical disassembly (0xsysenter.github.io) and confirmed our
own binary matches instruction-for-instruction. Launched fresh via
`debugserver <path>` (first time this project launched by path rather
than --attach, specifically to get ahead of an early startup check).

Set a breakpoint at the exact confirmed blr x8 executing
ptrace(0x1f, 0, 0, 0). Never fired. Tried a hardware breakpoint at the
same address (pure CPU debug register, zero memory writes) — also
never fired. Backtrace showed the process reaching a fully healthy
CFRunLoopRun with no crash, no anomaly.

Real, decisive follow-up finding: `thread list` showed only 3 threads
(main, GCD worker, UIKit event-fetch) — the extra thread viewDidLoad
is supposed to spawn via detachNewThreadSelector (running the
sysctl/task_get_exception_ports polling loop) never existed at all.
Not just the ptrace call — viewDidLoad's entire post-ptrace tail
appears skipped when launched via debugserver-by-path specifically.

### CB's question resolved the real mystery, and corrected our theory

CB asked whether MASTG specifically expects Frida/Objection rather
than an external LLDB/debugserver attach. Checked: MASTG-TECH-0084
documents the Mach-task-port technique (task_for_pid + Mach IPC) --
the same mechanism debugserver/LLDB uses -- as a legitimate,
documented MASTG technique in its own right, not Frida-exclusive. So
not a wrong-tool problem in that sense.

But this led to the real answer. A separate writeup (Bryce Bostwick,
"Debugging An Undebuggable App") documents the well-known real-world
signature of PT_DENY_ATTACH succeeding while a debugger is attached:
debugserver itself segfaults on attach, followed by a respring.

Tried this directly: launched UnCrackable L2 completely normally from
the iPad (no debugger present at any point during startup), then
attempted a normal `debugserver --attach=<pid>`.

  zsh: segmentation fault  /var/jb/usr/lib/llvm-16/bin/debugserver ...

Exact match to the documented signature. CONFIRMED: ptrace(PT_DENY_ATTACH)
is real and fully functional on iOS 18.7.2 -- when the app launches
normally, with no debugger present at any point. This revises what we'd
started to suspect (that this 2013-era technique might be dead code
on modern iOS) -- it isn't. The anomaly is specific to launching
fresh via debugserver-by-path, not to the technique itself. That
narrower mystery (why debugserver-by-path skips this code path) is
still open -- not resolved today, logged to BACKLOG.md rather than
chased further, since it wasn't blocking today's actual goal.

### Real-world value: independent confirmation of a known issue, precisely reproduced

This gives CB something genuinely useful to bring to Carlos (MASVS/MASTG,
NowSecure): not a new claim, but a precise, reproducible, address-level
confirmation of a known issue OWASP's own tracker (#1634) already
flags as unresolved, verified on current-generation iOS (18.7.2) with
a concrete methodology (disassembly cross-reference, hardware vs.
software breakpoint testing, process-health monitoring, and the
segfault-on-attach confirmation). Framed as "reproducible confirmation
of your own tracked issue, verified this way, on this iOS version" --
not overclaimed as new discovery.

### Status: real content confirmed, but unreachable via debugserver-by-path

Given attach-after-normal-launch is now proven blocked (by design,
once ptrace fires) and launch-by-path skips the whole code region for
reasons not yet understood, UnCrackable L2 was set aside for today's
actual goal (syscall annotation) rather than continuing to chase this
specific call site. Real, valuable finding either way -- logged fully
here for whenever this is revisited.

## Stage 3 — pivot to reliable content: DVIA-v2's own Plist write

CB's call (Option 2): stop chasing UnCrackable L2, validate against
completely reliable, already-proven content instead -- DVIA-v2's own
file-write challenges, using the --attach workflow that's worked all
week.

### First real finding: Keychain writes never touch the app's own process

Tried breaking on __open/__open_dprotected_np/__openat/__guarded_open_np
in libsystem_kernel.dylib, then interacted with DVIA-v2's Keychain
challenge (save a value). None fired, across a genuine write ("Data
saved" confirmed on screen).

Real architectural reason, not a MACE bug: SecItemAdd/SecItemCopyMatching
are XPC/Mach IPC calls to securityd, a separate system daemon that owns
the actual keychain database file. The app process itself never calls
open() on that file -- the real syscall happens inside securityd's own
process, which we were never attached to. Worth remembering for any
future syscall-validation attempt: Keychain is structurally the wrong
target for catching syscalls in the app's own process.

### Second real finding: Plist writes DO touch the app process, but still didn't fire

Switched to DVIA-v2's Plist challenge (NSDictionary.write(toFile:atomically:)
-- genuine, synchronous, in-process file I/O, no daemon involved).
Confirmed via two separate real writes ("Data saved in Plist," twice).
Same four libsystem_kernel.dylib breakpoints, still zero hits across
both writes.

At this point strongly suspected (WRONGLY, see below) that breakpoints
inside the dyld shared cache specifically don't work in this
environment -- every miss all day (Foundation two days ago, four
open-family symbols today, __ptrace and hardware-breakpoint attempts
against UnCrackable L2) had been inside shared-cache system libraries;
every hit had been app-owned __TEXT. This theory is corrected in Stage 5.

### Third real finding, mid-investigation: mace_grep Bug B recurred live

  mace_grep "write|atomically|documentsDirectory|dataFilePath|NSDictionary" \
    "disassemble -n _T07DVIA_v219PListViewControllerC21saveInPlistFileTappedyypF"
  -> only 1 of 770 lines matched

Same quote-stripping bug logged 2026-08-29 (Bug B, BACKLOG.md) --
pattern argument never gets its surrounding quotes stripped, only the
inner command does. The leading `"` corrupted the first alternative
("write -> `"write`, matching nothing) and the trailing `"` corrupted
the last (NSDictionary -> `NSDictionary"`, matching nothing). Dropping
the quotes entirely (no spaces in this particular pattern, so safe to
omit) gave the same single result both times -- coincidental overlap
with the corrupted `"write` alternative matching the disassembly
comment's own quote mark, not evidence the fix mattered here. Real,
reproduced instance of an already-logged bug; no new entry needed,
noted as a live recurrence.

### Fourth real finding: two NEW MACE bugs, caught live via a second thread

Single-stepping (stepi) toward the real writeToFile:atomically: call,
a genuinely new pthread got created mid-session (start_wqthread, normal
GCD worker-pool behavior, nothing to do with our target). MACE's panel
rendered for that stop too, on "Thread 32," and surfaced two real,
previously-unseen bugs:

1. Breakpoint ID malformed: rendered as "breakpoint
   18446744073709551612.1" -- almost certainly a -4 value misread as
   unsigned (2^64 - 4 = 18446744073709551612). Real formatting bug in
   _get_breakpoint_id() -- likely GetStopReasonDataAtIndex() returning
   a signed value that isn't being reinterpreted correctly, similar in
   spirit to (but a different bug from) the signed-x16 handling just
   added for syscall annotation this session.

2. ASLR offset nonsensical for this stop: shown as slide=0x...ac000
   offset=0x1fbaf1aa8, which doesn't correspond to pc - slide for
   this stop at all. Root cause: _compute_aslr_slide() always uses
   the MAIN app module's base (module index 0), which is meaningless
   once a stop happens inside a completely different image
   (libsystem_pthread.dylib here) on another thread. Both logged to
   BACKLOG.md as new, distinct entries -- neither blocks the actual
   annotation features, both are display/formatting bugs.

### Fifth: found and confirmed the real write, via mace_grep + real symbols

Rather than keep guessing keywords, used mace_grep against a broad
symbol search the same way that worked cleanly for iGoat two days ago:

  mace_grep Plist "image lookup -rn ViewController DVIA-v2"
  -> found saveInPlistFileTappedyypF cleanly, 32 of 2677 lines

Broke on the real handler, disassembled the actual function body,
found the real writeToFile:atomically: call site directly (mace_grep
again, correctly this time with quoting avoided). Caught it live:

  -- objc --
    [__NSDictionaryM writeToFile:atomically:]

Correct receiver AND selector, both resolved from live register
state on the real write -- a clean bonus confirmation the objc
annotation fix (2026-08-28) is holding up correctly on new content.

stepi'd through the objc_msgSend trampoline into libobjc.A.dylib's
real dispatch machinery, then used `finish` to skip the deep internal
frames rather than manually stepping through dozens of ObjC runtime
instructions with no realistic chance of reaching a raw syscall that
way. Confirmed x0 = 1 (write succeeded) but never reached a raw
svc #0x80 by this route either -- writeToFile:atomically: is too
deeply nested in Foundation internals for manual single-stepping to
be a practical way to reach the actual syscall.

## Stage 4 — the real fix: stop chasing a placed breakpoint, build the feature to recognize syscalls wherever encountered

Same reframe that fixed the objc annotation bug three days ago:
_is_objc_msgsend_call_site() doesn't require a placed breakpoint on
objc_msgSend -- it recognizes the pattern (a confirmed bl to the
objc_msgSend stub) at WHATEVER stop happens to land there. Applied the
identical idea to syscalls: _is_syscall_site() recognizes a real
"svc #0x80" instruction at pc, regardless of why the stop happened
(breakpoint, single-step, or otherwise) -- no need to place a
breakpoint on the syscall itself at all.

### Implementation

New ContextSnapshot fields: syscall_name, syscall_number (signed),
syscall_kind ("BSD" or "Mach trap"). New lldb_session.py functions:
_is_syscall_site() (confirms mnemonic == "svc" and operand contains
"0x80"), _annotate_syscall() (reads x16, reinterprets as signed 64-bit
to recover XNU's sign convention, looks up name in a small,
deliberately conservative BSD_SYSCALLS / MACH_TRAPS table). New panel
section in context_panel.py, same shape as the existing objc/swift
sections.

Key correctness detail, confirmed from real evidence this session:
AArch64/XNU uses the SAME svc #0x80 instruction for both BSD syscalls
and Mach traps -- distinguished only by the SIGN of x16 at the trap
(positive = BSD syscall number, negative = Mach trap number). Directly
confirmed live: libsystem_kernel.dylib's macx_swapon uses
"mov x16, #-0x30 ; svc #0x80" -- a Mach trap (-48), not a BSD syscall.
Handling both correctly, not just BSD, was essential.

Syscall/trap tables deliberately small and conservative -- only numbers
confidently sourced are included; anything else renders honestly as
"syscall #N" / "trap #N" rather than a guessed name. Same "fail safe,
not silently wrong" principle as the objc_msgSend call-site fix.
Comment in the code points future additions at XNU's actual source
(bsd/kern/syscalls.master, osfmk/mach/syscall_sw.h) rather than memory.

### Testing

7 new mock tests (real BSD syscall via ptrace=26; the EXACT live
macx_swapon Mach trap case, x16=-48, confirming correct sign handling
and honest fallback for an unrecognized number; a known Mach trap,
task_for_pid=-45; non-svc instruction correctly producing no
annotation; unrecognized BSD number falling back honestly; svc with a
non-0x80 immediate correctly ignored; panel rendering). Plus 2
regression tests confirming the objc_msgSend fix from 2026-08-28 still
works correctly after today's edits to the same file. All 9 pass.

One self-inflicted mid-session mistake, caught immediately: a
str_replace intended to add a docstring line matched the wrong
occurrence and briefly corrupted _annotate_objc_call's syntax (missing
opening docstring). Caught by the routine py_compile check before
anything was committed -- exactly the discipline this check exists for.

One live hand-off mistake during the M5 walkthrough: "sel_getName" was
given as a unique nano search anchor, but the actual
"except Exception: pass # Annotation is best-effort" text appears
TWICE in the file (end of _annotate_swift_location AND end of
_annotate_objc_call), so a plain text search for that phrase alone
would have landed the new code in the wrong (but harmless -- still
syntactically valid) location. CB caught this by inspecting the
surrounding context before pasting, exactly the "verify before
committing" discipline established this week. Confirmed via
grep -n "^def " showing correct placement before compiling.

## Stage 5 — live validation, and correcting a wrong theory

Went back to the exact call this whole project has seen at literally
every single fresh attach all week, but never actually annotated:
mach_msg2_trap, sitting at its natural resting point
(mach_msg2_trap + 8, a ret, right after its own internal svc #0x80
has already executed and returned -- confirmed this is why it never
misfired earlier: MACE was never actually stopped AT the trap
instruction itself before this session, always a few bytes past it).

Disassembled the function's true start, found the real instruction:

  libsystem_kernel.dylib`mach_msg2_trap:
      mov x16, #-0x2f      ; -47
      svc #0x80

Broke directly on the svc (0x1e8a84bf0, a shared-cache address,
consistent across processes on this device/build like every other
shared-cache symbol used this week). Continued.

FIRED IMMEDIATELY, first try:

  -- syscall --
    [trap #47]  (Mach trap)

x16 = 0xffffffffffffffd1 correctly reinterpreted as signed -47,
correctly classified as a Mach trap (not BSD), correctly reported
honestly as unrecognized (47 isn't in MACH_TRAPS) rather than guessed.
Exactly the designed behavior, validated live, first real attempt.

### Correcting today's "shared cache breakpoints don't work" theory

This breakpoint hit is itself the direct disproof of the theory
floated in Stage 3 -- mach_msg2_trap lives in the exact same
shared-cache image (libsystem_kernel.dylib) as every symbol that
failed to fire earlier today (__ptrace, __open and its siblings,
Foundation's fileExistsAtPath: two days ago). The real, better-
supported explanation, now that all the evidence is in: EVERY
failure today was either a genuinely one-shot call (ptrace, a single
ordinary open() call triggered once) or a call whose containing code
path was never actually executed on that specific run (UnCrackable
L2's entire post-ptrace viewDidLoad tail, confirmed absent via
thread list). mach_msg2_trap fires on essentially every run-loop
cycle -- a fundamentally different, far more forgiving target -- and
caught cleanly on the first attempt. Shared-cache placement was never
the actual variable; call frequency and whether the code path
genuinely executes were. Worth remembering this distinction precisely
for future debugging sessions rather than reflexively distrusting
shared-cache breakpoints, which are demonstrably fine.

## Status

Syscall annotation: DONE. Built using the pattern-recognition approach
(no placed breakpoint needed), correctly handles both BSD syscalls and
Mach traps via x16's sign, validated live against real, frequently-
recurring content (mach_msg2_trap) on the first real attempt. All v1
checklist features are now built.

Real, valuable secondary findings from today, all logged: UnCrackable
L2's ptrace(PT_DENY_ATTACH) confirmed genuinely functional on iOS
18.7.2 (reproducible confirmation of OWASP's own known issue #1634,
worth bringing to Carlos/NowSecure); Keychain writes structurally
bypass the app's own process (securityd XPC); two new display-bug
findings (malformed breakpoint ID, wrong-module ASLR offset on
cross-image stops); one live recurrence of an already-tracked
mace_grep bug; and one theory (shared-cache breakpoints don't work)
proposed, tested further, and correctly retracted rather than left
standing.
