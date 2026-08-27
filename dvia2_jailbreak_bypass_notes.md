## Target
- App: DVIA-v2 (Damn Vulnerable iOS App v2, Prateek's app)
- Container: /var/containers/Bundle/Application/2D4F8049-C960-462D-BDF1-4A38ED12443F/DVIA-v2.app
- Device: palera1n iPad 7th Gen, rootless jailbreak (Sileo, not Cydia)
- Challenge: Jailbreak Detection (5 tests)

## Purpose

First MACE-native validation against a target genuinely unrelated to
MACELocalAuthTest -- different app, different developer, real
Objective-C content rather than Swift-wrapped framework calls. Two
things needed a second, independent target before they could be
called generalized rather than overfit to one harness:

1. Passive objc_msgSend annotation (ROADMAP.md marked "in progress" --
   every prior validation was Swift code calling into an Apple
   framework, never genuine ObjC dispatch)
2. mace_patch (validated 2026-08-23 on MACELocalAuthTest only)

## Symbol discovery

DVIA-v2 is itself a Swift app (old-style Swift 4 mangling,
`_T07DVIA_v2...`), same shape as MACELocalAuthTest. Found via:

  image lookup -rn "jailbreak"

15 matches, all under JailbreakDetectionViewController. Five UI
handlers (jailbreakTest1Tapped through jailbreakTest5Tapped) plus one
bare jailbreakTest3 (no "Tapped" suffix) -- the actual detection logic
the Tapped handler calls into.

## Lesson: `br set -n` unreliable on Swift symbols, `--shlib` is the fix

`br set -n "jailbreakTest3"` failed ("no locations (pending)") the
same way plain name-based breakpoints failed on MACELocalAuthTest all
week. This session found a cleaner fix than the manual slide-arithmetic
approach used previously:

  br set -a <file_relative_address_from_image_lookup> --shlib DVIA-v2

lldb resolves the slide internally and prints back the demangled
symbol name it landed on, confirming the match. This is strictly
better than manually computing `slide + file_offset` by hand -- two
separate hand-arithmetic mistakes were made and caught this session
(dropped digits going from 0x1001cbdac to a runtime address) before
switching to --shlib exclusively for fresh file-relative addresses.
--shlib is NOT needed for addresses already resolved from a prior
--shlib call or from `image lookup` at a live breakpoint stop --
those are already runtime addresses.

## Stage 1 -- Test 3, real ObjC content found

jailbreakTest3 (file offset 0x10019523c) is a direct inline check:

  bl _T0So11FileManagerCMa              ; FileManager type metadata
  ...
  adrp x8, 674 / add x8, x8, #0xf50     ; "defaultManager" selector
  bl objc_msgSend                       ; [NSFileManager defaultManager]
  ...
  adrp x8, 456 / add x8, x8, #0x8a0     ; "/Applications/Cydia.app"

Classic technique: [NSFileManager defaultManager]
fileExistsAtPath:@"/Applications/Cydia.app".

### objc annotation validated on real content

mace_swift_load failed as expected (DVIA-v2 is not built from local
DerivedData -- see swift_context.py's documented fallback chain).
Proceeded without it: _annotate_objc_call's PRIMARY path resolves the
receiver via the live ObjC runtime directly (object_getClassName on
x0, sel_getName on x1) and does not require SwiftContext at all --
SwiftContext is only the fallback when the runtime lookup fails. This
made DVIA-v2 a clean isolated test of the runtime-lookup path alone.

  br set -a <objc_msgSend call address>
  c

  -- MACE panel --
  objc
    [NSFileManager defaultManager]

First real confirmation of passive objc_msgSend annotation against
genuine Objective-C dispatch. Every prior validation (MACELocalAuthTest)
was Swift code calling an Apple framework -- structurally different
from this.

### Result: naturally false on this device -- expected, not a MACE gap

App reported "Device is Not Jailbroken" with zero patching. Two
independent reasons this specific check can't catch this setup:
1. palera1n here is rootless -- installs under /var/jb/..., not
   /Applications/Cydia.app.
2. Even a rootful jailbreak running Sileo (not Cydia) would also miss
   this exact hardcoded path -- it only checks for one specific
   package manager's install location, not the class of tool.

## Stage 2 -- Tests 1 and 2, tracing to the shared choke point

jailbreakTest1 and jailbreakTest2 don't inline their checks -- both
call into `DVIAUtilities` via indirect dispatch (blr, not bl), so
static disassembly alone can't follow them further without knowing
the target.

  image lookup -rn "DVIAUtilities"

Found the real target: not detection logic, but a shared UI helper --

  showAlert(forJailbreakTestIsJailbroken: Sb, viewController:)
  (mangled: ...showAlertySb28forJailbreakTestIsJailbroken_...)

Sb = Swift's mangled Bool. Hypothesis: every test's computed detection
result funnels through this one function before displaying its alert
-- meaning it's a better patch target than chasing five separate
detection techniques individually.

  br set -a <showAlert file offset> --shlib DVIA-v2
  c  (tap Test 1)

Confirmed: lr traced straight back into jailbreakTest1's body. x0 = 0
(false) -- Test 1 also naturally misses this device, same as Test 3.

### Test 2 -- real library-based check, still misses this device

jailbreakTest2's disassembly showed a materially different technique
from Test 3's single hardcoded path:

  bl _T0So18JailbreakDetectionCMa      ; JailbreakDetection class ref
  adrp x8 / add x8 ... "isJailbroken"  ; selector
  bl objc_msgSend                      ; [JailbreakDetection isJailbroken]

`JailbreakDetection` strongly suggests a bundled third-party detection
library (broader battery of checks: sandbox writes, suspicious dylibs,
fork() tests -- not just one file path), not just an inline check.
Broke immediately after the call returns (w0 holds the Bool result):
still x0 = 0 -- even this more robust, library-based check missed the
rootless setup. Useful signal on its own: rootless jailbreaks appear
to evade at least this detection library entirely, not just the naive
single-path checks.

## Stage 3 -- mace_patch validated on second unrelated target

Rather than continue hunting Tests 4/5 for a natural true positive,
proved the mechanism directly at the confirmed real boolean result
from Test 2's [JailbreakDetection isJailbroken] call:

  mace_patch w0 1
  c

  [MACE] w0: 0x0 -> 0x1  at 0x10462ad80 in jailbreakTest2Tapped
  (breakpoint 9.1)

Continued through showAlert -- confirmed x0 = 0x1 arrived there
correctly (patch propagated through the call chain), then:

Result: "Device is Jailbroken" (previously "Device is Not Jailbroken"
on every prior natural run).

### Status

mace_patch confirmed working end-to-end on a target sharing nothing
with MACELocalAuthTest -- different app, different developer, real
ObjC library dispatch rather than an Apple framework call. Target-
independence validation bar (at least two unrelated targets) now met
for mace_patch. ROADMAP.md updated accordingly.

## Bugs found -- both real, both located precisely, neither MACE-target-specific

Both surfaced specifically BECAUSE this was an unfamiliar target --
neither would have been found continuing to validate against
MACELocalAuthTest alone. Exactly what target-independence testing is
for.

### Bug 1 -- address-range heuristic (pre-existing, now confirmed on a second target)

Already flagged and annotated 2026-08-23 (see BACKLOG.md, Context
Panel v2 section). Not re-triggered this session in a new way, but
DVIA-v2 is now a second real target on the list that would validate
the eventual SBProcess.GetMemoryRegionInfo() fix, alongside
MACELocalAuthTest.

### Bug 2 -- NEW: selector resolution fires without confirming a real objc_msgSend call site

_annotate_objc_call's gate for "try to resolve x1 as a selector" is
only "is x1 a number bigger than 0x100000000" -- it never confirms
we're actually at or near a real objc_msgSend call before running
sel_getName() on whatever x1 happens to contain.

Reproduced twice this session, at two different DVIA-v2 stops that
were NOT objc_msgSend call sites (a Swift static function entry, and
a Swift class method entry):

  -- objc --
    [? ]ʍ\U00000004\xa1\xa5]        (showAlert entry, x1 = a real
                                      UIViewController pointer)

  -- objc --
    [? class]                        (jailbreakTest2Tapped entry,
                                      x1 = coincidentally a real
                                      selector value, but wrong context)

Root cause: on the modern ARM64 ObjC runtime, a SEL is literally a
pointer directly into the interned selector string table.
sel_getName() does no validation -- it just reads memory from that
address as a C string until a null byte. Given any large/pointer-
shaped value in x1 that isn't actually a selector, it walks into
whatever real memory is there (an object's isa pointer and ivars, in
the first case above) and returns those raw bytes as if they were text.

Two failure shapes observed, and the second is the more dangerous one:
- Garbled/unprintable output (obviously wrong, easy to distinguish)
- A real, legitimate-looking selector name (`class`) that is
  nonetheless attributed to the wrong context entirely -- exactly the
  case a researcher would be least likely to question.

Not filed as a fix this session -- documented and logged to
BACKLOG.md as its own entry, separate from Bug 1, pending a decision
on priority/scope.
