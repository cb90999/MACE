## Target
- App: iGoat-Swift (OWASP/iGoat-Swift, prebuilt IPA from repo root)
- Container: /var/containers/Bundle/Application/F623B1B2-2DC0-4B78-A9A0-2B1EB673057A/iGoat-Swift.app
- Device: palera1n iPad 7th Gen, rootless jailbreak (same as all week)
- Setup: Option B — downloaded prebuilt iGoat-Swift.ipa, resigned with
  zsign (~/Documents/Certificates.p12, wildcard profile
  4bcbae7e-ffb9-486b-851f-53927ef70875), installed via
  `ideviceinstaller install` (note: subcommand is `install`, not `-i`
  — same correction needed again this session, already documented
  in an earlier chat's summary; worth actually internalizing this
  time rather than re-deriving it live again)

## Goal for the day (per ROADMAP.md)

iGoat is the named Priority 1 target specifically for validating
**syscall annotation** (svc #0x80 + x16) — a completely unbuilt v1
feature, the actual reason iGoat was picked over other remaining
targets. Not achieved this session — see "Status" at the end.

## mace_grep — first live validation, working correctly

Before any of the investigation below, confirmed mace_grep works
exactly as designed on real large output:

  mace_grep DVIA "image list -o -f"
  → 25 of 747 lines match 'DVIA'

Filtered the same 700+-line module dump that had to be manually
eyeballed two sessions ago. Real, working validation — not just a
demo — of the tool built specifically to solve that problem.

## Challenge menu navigation — no "Jailbreak Detection" category this time

Unlike DVIA-v2, iGoat-Swift's categories don't include an explicit
"Jailbreak Detection" top-level entry. Found the actual jailbreak
check under Runtime Analysis > "Method Swizzling" (title refers to
the *bypass technique* the challenge teaches, not the check's own
implementation naming — this distinction caused most of today's
wasted searching, see below).

"Runtime Analysis" > "Runtime Analysis" (first entry, same name as
category) was tried first and is NOT a debugger/jailbreak check —
it's a UI-inspection puzzle ("A Secret Is Found In The Hidden
Label!"), a different OWASP category entirely despite the similar
name.

## The real problem: hours spent searching for the wrong identifiers

Spent most of the session trying `image lookup -rn "<term>" iGoat-Swift`
for every plausible keyword drawn from on-screen UI text: "jailbreak",
"attach", "verify", "swizzl", "ViewController", even "main". All came
back empty. Two confounding factors stacked on top of each other and
took a long time to separate:

### Confounder 1 — `image lookup -rn <pattern> <module>` is unreliable for this module

Proven working correctly against libsystem_kernel.dylib (found the
real `__ptrace` symbol, 2 matches) and against Foundation (found
`-[NSFileManager fileExistsAtPath:]` cleanly, 6 matches) — both times
via the exact same syntax. But the identical syntax against
iGoat-Swift returned silent, unexplained empty results for terms that
should exist, INCLUDING "main", which every compiled executable has
as a symbol. This is a real, reproducible discrepancy: same command
shape, works for two different system libraries, silently fails for
this specific app module. Not yet root-caused. Logged to BACKLOG.md.

### Confounder 2 — the app's own symbol table really is stripped

Independently confirmed via `image dump symtab iGoat-Swift` (routed
through mace_grep once the direct approach kept producing walls of
output) — 9475 total entries, but every single `OBJC_CLASS_$_` entry
is marked `Undefined` (i.e. imported from Apple/Realm frameworks,
none of them iGoat's own classes). This is a genuine, real difference
from every prior target this project: MACELocalAuthTest and DVIA-v2
were both builds with full Swift symbol tables (old-style `_T0...`
mangling everywhere); this prebuilt iGoat-Swift IPA is a standard
stripped Release build. Confirmed a search for "MethodSwizzlingExerciseVC"
(the real class name, found via strings — see below) also returns zero
matches in the symtab dump, proving the app's own type/method symbols
are genuinely absent, not just hard to find.

First real stripped-Release target this project has worked against.
Worth treating as a positive, not just friction — this is closer to
what a hardened, distributed app actually looks like than any prior
target this week.

### Resolution — strings extraction on the real binary, not symbol search

Stopped guessing keywords against symbol tables entirely and pulled
strings directly from the actual Payload binary:

  cd ~/Documents/MobileBinaryTargets/ios/crackmes/iGoat-Swift
  mkdir -p extracted && unzip -q original/iGoat-Swift.ipa -d extracted
  strings extracted/Payload/iGoat-Swift.app/iGoat-Swift \
    | grep -iE "ptrace|jailbrok|cydia|ismethodswizzl|swizzl" | sort -u

Real, unambiguous answer in one command:

  _TtC11iGoat_Swift25MethodSwizzlingExerciseVC
  /Applications/Cydia.app
  MethodSwizzlingExerciseVC
  This app is not running on a jailbroken device
  This app is running on a jailbroken device

Confirms: real class name is `MethodSwizzlingExerciseVC` (not
"swizzl" as a naming fragment anywhere — hence every earlier keyword
guess failing), the check is the classic `/Applications/Cydia.app`
path check (same technique as DVIA-v2 Test 3), and critically — **no
"ptrace" string anywhere in this binary at all**. This challenge does
not use process-tracing as a technique. Confirms Method Swizzling was
the wrong challenge for today's actual syscall-annotation goal,
independent of any of the symbol-search friction above.

Lesson worth carrying forward explicitly: when symbol search comes up
empty against an unfamiliar/stripped target, strings extraction on the
real binary is a faster, more reliable ground-truth check than
continuing to guess keywords — should be an earlier step next time,
not a last resort after already exhausting many guesses.

## Confirming the Cydia check (inconclusive due to environment)

Since Foundation's fileExistsAtPath: symbols aren't stripped
(system framework, not app code), tried breaking there directly to
sidestep iGoat's stripped symbol table entirely:

  image lookup -rn "fileExistsAtPath" Foundation
  → -[NSFileManager fileExistsAtPath:] @ 0x181872f44

  br set -a 0x181872f44
  → warning: failed to set breakpoint site at 0x181872f44 for
    breakpoint 2.1: error: 9 sending the breakpoint request
  → lldb still reports "Breakpoint 2: address = 0x0000000181872f44"
    despite the warning

Continued, tapped Verify Status again. App correctly showed "Not
Jailbroken" (consistent with the Cydia check running normally) but
the breakpoint never fired. Given the explicit insertion-failure
warning, this is real, direct evidence the breakpoint's physical trap
write likely failed — NOT evidence the code path wasn't hit. Result
is genuinely inconclusive: we have indirect behavioral confirmation
(the alert text matches what the Cydia check should produce) but no
direct confirmation via breakpoint hit.

Retroactive open question this raises: this morning's first `__ptrace`
breakpoint (libsystem_kernel.dylib, no insertion warning shown) never
fired either, across every iGoat challenge tried. No warning is a real
point in its favor, but we never got independent confirmation it
actually worked — worth keeping in mind rather than either fully
trusting or fully discounting that earlier result.

## Status

Syscall annotation (today's actual goal) — NOT built. Method Swizzling
confirmed to be the wrong challenge (Cydia-path check, no ptrace
anywhere in the binary) — real progress, but a dead end for this
specific goal, not a partial success.

Next session: return to iGoat's other challenges (Tampering, Binary
Patching, or others not yet explored) specifically hunting for real
ptrace/syscall content, now equipped with the right lesson learned —
extract strings first, don't guess symbol names against a target
until its symbol-table completeness is actually confirmed.
