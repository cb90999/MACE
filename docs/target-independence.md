# Target Independence

A standing engineering discipline for MACE, not a one-time checklist.
Captured Aug 2026 following external repo review (full review in
docs/user-feedback.md, 2026-08-23 entry); keep this doc in
sync as the definition sharpens.

## The principle

> MACE may recognize platform patterns; it should never recognize the
> test case.

This is deliberately **not** "no hardcoded constants." MACE's code is
full of true, load-bearing constants — the `objc_msgSend` calling
convention, Mach-O section names, the AArch64 ABI, `svc #0x80` as the
syscall instruction, Swift's runtime metadata section layout. Knowing
these is the entire point of a platform-aware tool. Banning constants
would just produce worse code, not more generalized code.

The actual test is narrower and sharper:

> **Does this logic's correctness depend on knowing which particular
> test binary is running, or only on knowing the platform it runs on?**

`objc_msgSend`, Objective-C method encoding, the AArch64 ABI, Mach-O
metadata, Swift metadata, JNI conventions, `LocalAuthentication`
framework symbols — legitimate platform intelligence. True for any
binary on that platform.

A hardcoded bundle ID, a specific class name, a selector that only
exists because the current harness happens to define it, an address
range observed from watching one app's stack on one device in one
session — overfitting, even though none of it looks like a "magic
string" in the traditional sense.

## Development fixtures vs. validation targets

`MACELocalAuthTest` and `MACESecurityTest` are controlled harnesses
built specifically to develop and exercise MACE features. That's
their job — it's fine and expected for early feature work to happen
against them.

DVIA v2, the 8ksec challenges, MobileHackingLab, and eventually real
production apps are **effectively unseen validation data**. A feature
isn't "done" because it works against the harness it was built
against; it's done when it survives contact with a target that had no
influence on how it was written.

Do not modify the generic implementation merely to make one target's
demo look successful, unless the change encodes an actual reusable
platform pattern. If a target breaks a feature, that's useful signal,
not a bug to be silently special-cased away.

## When something breaks on an independent target

Ask, in this order:

1. **Was the assumption wrong?** (e.g. an address range or offset
   that was only ever true for the dev fixture's build/session)
2. **Was the parser too narrow?** (e.g. only handles one exact LLDB
   output shape, one compiler-optimization level, one Swift version)
3. **Is this genuinely platform-specific behavior** that the new
   target simply doesn't exhibit? (not a bug — just means the feature
   correctly doesn't apply here)
4. **Is this a capability MACE doesn't have yet?** (legitimate gap —
   goes in `BACKLOG.md`, not patched around)

This is a materially better loop than adding special cases until every
demo passes. A tool whose correctness was accumulated one target-shaped
patch at a time isn't ground truth — it's a collection of anecdotes
that happen to look right in a demo.

## Red flags to watch for in review

- Hardcoded bundle IDs, executable names, class names, selectors,
  file paths, absolute offsets, or symbol names
- Assumptions that a specific framework is always present
- Fixed register meanings asserted outside the ABI or the current
  call context
- Absolute addresses used instead of image-relative offsets or
  proper symbol/region resolution
- Logic that depends on one specific DerivedData directory layout
- "Special case" branches keyed to a named test app (`MACELocalAuthTest`,
  `MACESecurityTest`, `DVIA`, etc.)
- Parsers that only work against one exact LLDB output shape

## Annotation convention

When target-specific logic is genuinely necessary — in the test
harness itself, in a target-specific adapter, or as a deliberate,
temporary experiment — mark it unmistakably rather than letting it
blend into core logic:

    # TEST-HARNESS ONLY

or

    # TODO: generalize before merge

Visible technical debt is fine. Technical debt that looks like
finished platform intelligence is not.

## Validation bar

Before calling a new feature generic, validate it against **at least
two unrelated targets** — not two builds of the same harness app, two
genuinely different binaries/apps. If the same MACE feature behaves
correctly across both, it has earned the label "generalized." One
successful target is a demo, not evidence.

## Worked example: the address-range heuristic (Aug 2026)

`_annotate_objc_call()` in `lldb_session.py` distinguishes stack
addresses from real object pointers using a hardcoded range
(`0x160000000`-`0x17fffffff`) and a `0x100000000` pointer-vs-small-int
threshold. Both were empirically observed from watching register
values on one palera1n iPad running iOS 18.7.2 across the sessions
that built this feature — not derived from an actual memory-region
query, and not a documented ABI guarantee.

This passed a naive "no hardcoded strings" check cleanly (it's a
numeric range, not a magic string) but fails the target-independence
test: its correctness depends on this device's/session's observed
memory layout, not a platform invariant. On a different device, iOS
version, or ASLR configuration, it could silently mis-annotate — or
silently fail to annotate at all, with no visible error.

Flagged, annotated in place with a `TODO: generalize before merge`,
and tied to its proper fix (`SBProcess.GetMemoryRegionInfo()`-based
region classification — see `BACKLOG.md`, Context Panel v2) rather
than patched with a wider numeric guess. The real fix will need
validation against DVIA v2 and the 8ksec targets before it can be
trusted as generalized, per the validation bar above.
