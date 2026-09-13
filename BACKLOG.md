∑# MACE Backlog

Ideas and future research threads. No version commitment.
Everything here is parked, not forgotten.

## AArch64 Analysis
- PAC-aware backtrace handling (iOS A12+, Android Tensor G4)
- PLT/GOT region annotation in context panel
- Inline hook detection — entry point integrity check
- Heap pointer dereference — follow xN into heap memory
- SVC hidden function call detection (fatalsec/renef pattern)
- Obfuscation CTF binary — IOCCC-style compiler obfuscation target

## Platform
- iOS 26 / usbliter8 BootROM exploit target (iPhone 11, A13)
- Android kernel KGDB via USB-Cereal (Pixel 10a)
- vphone-cli iOS emulator integration
- MASTG KeyStore / crypto key material capture

## AI Layer
- colibri/GLM-5.2 evaluation as local inference tier
- Register pattern recognition — flag check, crypto primitive, loop detection
- objc_msgSend selector annotation
- Syscall argument interpretation from register state

## Toolchain
- pyproject.toml — proper pip installable package
- Portable path resolution (replace hardcoded _MACE_SRC)
- MACE session config file (.macerc)
- GitHub repository — public open source release

## Research References
- fatalsec renef — SVC direct syscall, libantifrida.so. UPDATE
  2026-09-04: r2renef/renef confirmed Android-only (not an iOS
  Frida/MACE-coexistence fix — that question remains open). Still
  architecturally in-process injection like Frida itself (Lua-
  scripted, explicitly modeled on r2frida), just a different engine —
  real Android v2 tooling worth comparing against libantifrida.so, not
  a workaround for the iOS coexistence problem.
  UPDATE 2026-09-05 (research log, fatalsec YouTube — "Finding hidden
  function calls using SVC instruction"): real, concrete grounding for
  why syscall annotation (built and validated 2026-08-30) matters
  beyond a general capability. The video documents a genuine evasion
  technique: a binary that issues raw ARM64 SVC instructions directly,
  bypassing libc wrapper functions (open, read, etc.) entirely, so
  those symbols never appear in the import table and never get called
  at all. Their own workflow to find these: radare2 `/A/ SVC` to
  locate the instructions, read the syscall number from x8 (Linux/
  Android convention — confirms the same register already targeted in
  ROADMAP.md's v2 checklist), map it via arm64.syscall.sh.
  Worth a precise correction to the framing floated in conversation
  before checking this source: it's not that Frida "can't see" direct
  syscalls at all — the video's own dynamic-interception step is
  "develop Frida scripts to hook the SVC instruction," which works
  fine once you know the address. The real, narrower, more honest
  MACE advantage: _is_syscall_site() recognizes the svc #0x80/#0
  pattern automatically at ANY stop (single-stepping, an unrelated
  breakpoint nearby, incidental exploration) — no separate static
  pre-analysis pass required first to find where to place a hook, the
  way this video's whole radare2 workflow exists to do.
  Two concrete resources for v2's eventual LINUX_SYSCALLS table, worth
  building against directly rather than from memory (same discipline
  as the iOS BSD_SYSCALLS/MACH_TRAPS tables): arm64.syscall.sh for
  Linux syscall number lookups, and radare2's `e asm.os = linux` +
  `/as` command, which auto-maps syscall numbers to names — a
  plausible authoritative source worth checking directly when that
  table gets built.
- xairy pixel-kgdb — Android kernel debugging, PAC backtrace corruption
- IOCCC 2025 uellenberg — compiler obfuscation techniques
- Garuda Defender APK — anti-debug detection analysis (Thursday)
- 8ksec OAAE — ARM exploitation cert, MACE as study environment.
  UPDATE 2026-09-05: confirmed 8kSec has a dedicated "Offensive iOS
  Internals" course (academy.8ksec.io), not just general ARM64 —
  covers SPTM/TXM/PAC/PAN/PPL mitigations, ARM64 internals, lldb-based
  debugging, dynamic instrumentation, exactly MACE's actual domain.
  Lead instructor across the whole 8kSec course lineup is Prateek
  Gianchandani — the same author of DVIA-v2, MACE's single most-used
  validation target this whole project. Worth treating "Offensive iOS
  Internals" as the closest-fit course reference, not the more general
  "Offensive Mobile Reversing and Exploitation" (iOS+Android combined)
  or "Practical Mobile Application Exploitation" (broader app-security
  testing, Frida/Burp/MobSF-centric) courses also in the lineup.
- MobileHackingLab iOS writeups index (lautarovculic.github.io/writeups,
  research log 2026-09-05) — real, credentialed researcher (active
  HackerOne/Bugcrowd bounty profiles, not anonymous), dozens of worked
  MHL iOS challenge writeups in one place (Captain Nohook, Config
  Editor, Cyclic Scanner, Run Time, Serial/Secure Notes, TokenBleed,
  Gotham Times, and more). The one writeup actually read (Gotham
  Times) turned out to be a URL-scheme/network-interception vuln —
  static triage plus Burp, no live register work at all — a real,
  useful reminder that not every MHL iOS challenge is a MACE fit.
  Genuine value of this resource isn't any single writeup, it's using
  the INDEX to pre-screen for the "ultimate test" MHL target
  deliberately (genuine anti-debug/jailbreak-detection/native ARM64
  content) before committing real session time, avoiding a repeat of
  the iGoat Tampering/Method-Swizzling mistake (two challenge names
  that turned out to be the literal same file, discovered only after
  hours of live investigation). Candidate names worth checking first
  based on title alone, NOT yet confirmed by reading: "Run Time",
  "Cyclic Scanner" — sound most likely to involve runtime/anti-debug
  content, but this is a guess from naming, not verified.

- node-applesign (pancake/NowSecure) as preferred re-signing tool for
  entitlement-sensitive targets — use -M (massage-entitlements) to
  preserve original app entitlements while removing only privileged ones.
  Replace zsign in ios-setup.md when validated.
  Repo: https://github.com/nowsecure/node-applesign

## Context Panel v2 — Human-First Display
Source: External usability feedback (Aug 2026)

Current gap: MACE panel shows same information as LLDB, just better formatted.
GEF shows MORE information than GDB, surfaced automatically.
Target: Panel must be genuinely useful standalone before AI layer lands.

### Priority improvements:

1. Pointer dereferencing
   Resolve pointer values to human-readable content inline
   x0 = 0x302cf3a50 -> "i am groot!" (NSString)
   x27 = 0x104a714e0 -> MACESecurityTest.__DATA.__objc_const
   Implementation: SBProcess.ReadMemory() + string heuristic

2. Changed register highlighting
   Registers modified since last stop -> highlighted color
   Unchanged registers -> dimmed
   Implementation: ContextSnapshot diff between iterations

3. Memory region labeling
   Append [heap], [stack], [binary.__TEXT], [dylib] to pointer values
   x0 = 0x302cf3a50 [heap]
   x26 = 0x104a714e0 [MACESecurityTest.__DATA]
   Implementation: SBProcess.GetMemoryRegionInfo()
   This also fixes existing debt: _annotate_objc_call() in
   lldb_session.py currently distinguishes stack addresses from object
   pointers via a hardcoded range (0x160000000-0x17fffffff) and a
   0x100000000 pointer-vs-small-int threshold, both empirically
   observed on one palera1n iPad/iOS 18.7.2 session rather than derived
   from actual memory region info. Flagged by external repo review
   (Aug 2026, full review captured in docs/user-feedback.md) as a
   target/device-specific heuristic living in core code  
    -- would need validation against DVIA v2, 8ksec, and other targets
   before trusting it generalizes. See docs/target-independence.md for
   the general principle this instance exemplifies. Real fix is this
   GetMemoryRegionInfo() work, not a patch to the numeric range.
    UPDATE 2026-08-27: DVIA v2 is now a real second target for
   validating the eventual fix (see dvia2_jailbreak_bypass_notes.md) --
   this heuristic was not re-triggered in a new way this session, but
   a related, separate bug WAS found in the same function; see below.
   UPDATE 2026-08-28 (research log): both DVIA v2 and MACELocalAuthTest
   are PAC-free A10 targets -- neither actually tests whether this
   heuristic (or the objc_msgSend call-site fix in 3b below) holds up
   on a PAC-enabled chip, which is the real generalization risk here,
   not just "a second app." github.com/jprx/darwin-vm (QEMU fork,
   SPTM/TXM/MIE-aware) may be the fastest way to get a PAC-enabled
   validation target without waiting on real hardware: boots actual
   Darwin (iOS 26.6, even 27.0 beta) kernels to a root shell across
   A14-A19, no jailbreak required, and exposes a GDB Remote Serial
   Protocol debug server confirmed lldb-compatible in its own docs --
   the same protocol MACE's connection layer already speaks, so no
   MACE code changes should be needed to point at it. NOT a general
   MACE test platform -- explicitly no SpringBoard/app UI/touch
   interaction (own README: "don't expect... GUI apps... springboard
   to work"), so it can't run DVIA-v2.app or MACELocalAuthTest.app as
   real apps. Narrow, real value: a command-line, PAC-enabled dev
   fixture (compile + codesign a small test program locally, run it
   under the VM) to validate register/pointer/annotation logic against
   PAC before the iPhone 11 (A13) hardware jailbreak path exists --
   see "usbliter8" thread in chat history, RP2350 purchase planned
   after Sept 20, timeline uncertain. This is available now instead.
   UPDATE 2026-09-04 (research log, earlier this week): the actual
   usbliter8 disclosure (Paradigm Shift, June 18 2026, coordinated
   with Apple Product Security) explicitly names the iPhone 11 (A13)
   as affected, and -- unlike the A14/M1 pattern documented separately
   at proteas.github.io (where only early/pre-production silicon was
   vulnerable, patched before real consumer devices shipped) -- the
   researchers' own words confirm A12/A13 stayed vulnerable for their
   FULL production lifetime: "affected A12 and A13 devices will carry
   it for the remainder of their lifetime." Real, store-bought
   hardware is not excluded the way it is on A14/M1. Also found a
   second, more actively developed tool -- Trussh/usbliter8 -- claiming
   full A12/A13 coverage across iOS 17-27 (would include the actual
   26.6 build) with dedicated SPTM/TXM patchfinders for iOS 27's CTRR
   lockdown, plus a claimed "11/11 devices, 100% success rate" (treat
   with the same caution as any unverified README claim). Worth
   checking both this tool and Leeksov/usbliter8ra1n's own progress
   again closer to the actual Sept 20+ purchase date.
   UPDATE 2026-09-04 (research log, earlier this week): a
   MobileHackingLab writeup on JOP/PAC surfaced a real, narrow gap in
   mace_patch's own validation coverage, distinct from the annotation-
   heuristic question above. Every mace_patch write validated so far
   (LocalAuthTest, DVIA-v2) has been a plain integer (x0=1, w0=1,
   x0=0x1f) on a PAC-free A10 device. PAC signs pointer values (return
   addresses, some function pointers) with a signature tied to the
   pointer's value and execution context; overwriting a signed pointer
   with an unsigned/incorrectly-signed one traps at the point of use,
   not at the write itself.
   Follow-up research refined this into a real, well-reasoned
   hypothesis rather than an open unknown: the PAC signing
   INSTRUCTIONS (pacia, pacda, etc.) are genuinely available at
   userspace/EL0 -- confirmed directly in the original ARMv8.3 kernel
   patch series -- and the CPU applies the correct per-process key
   transparently based on execution context, without ever exposing the
   raw key value. This is exactly why Frida's own hooking/patching
   (Interceptor.attach, NativeCallback, Arm64Writer instruction
   patches) works normally on modern PAC-enabled iPhones: Frida's
   injected code runs COOPERATIVELY, within the target process's own
   execution context, so it can legitimately sign new pointer values
   the same way any normally-compiled PAC-aware program does. mace_patch
   sits in the SAME cooperative category -- writing through a
   legitimately-attached debugger to a genuinely stopped process, not
   forging a value via memory corruption with no legitimate execution
   context at all (which is what PAC actually defends against, and
   what neither Frida nor MACE do or need to do). The likely answer,
   then, is that mace_patch probably CAN correctly write pointer values
   on PAC-enabled hardware, for the same structural reason Frida's
   pointer-writing already does -- but this is still a hypothesis, not
   a confirmed result. Worth testing explicitly once a PAC-enabled
   validation target exists (see darwin-vm above, or the iPhone 11
   hardware path) rather than assuming either way.
   UPDATE 2026-08-30: CB flagged a live, concrete motivating example
   for this exact item, reviewing a real raw panel screenshot (DVIA-v2,
   mach_msg2_trap stop) -- x0/x1/x3/x5 all shown as large, meaningless
   unsigned decimals (e.g. x0 = 6127837432u) when they're genuinely
   stack/pointer addresses. Decimal tells a researcher nothing hex
   doesn't already show better for address-shaped values -- exactly
   the gap this backlog item exists to close. Worth citing this
   screenshot/example directly when the GetMemoryRegionInfo() work
   happens, as a concrete "why this matters" case beyond the abstract
   description above.

3b. _annotate_objc_call fires selector resolution without confirming
    a real objc_msgSend call site
    Discovered: 2026-08-27, DVIA-v2 session
    (dvia2_jailbreak_bypass_notes.md)

    _annotate_objc_call's gate for attempting selector resolution on
    x1 is only "is x1 numerically > 0x100000000" -- it never verifies
    the current stop is actually at or immediately after a real
    objc_msgSend-family call before running sel_getName() on whatever
    x1 happens to contain.

    Reproduced twice against DVIA-v2 at stops that were plain Swift
    function/method entries, not message-sends:

      -- objc --
        [? ]ʍ\U00000004\xa1\xa5]   (x1 = a real UIViewController
                                     pointer, not a selector)
      -- objc --
        [? class]                  (x1 = coincidentally a real
                                     selector value, wrong context)

    Root cause: on the modern ARM64 ObjC runtime, a SEL is literally a
    pointer into the interned selector string table. sel_getName()
    does no validation -- it reads raw memory from that address as a
    C string. Any pointer-shaped non-selector value in x1 gets walked
    as if it were one, printing whatever real memory is there (an
    object's isa/ivars, in the first case above).

    The second failure shape is the more dangerous of the two: a
    real, legitimate-looking selector name (`class`) attributed to
    the wrong context entirely, rather than obviously-garbled output
    a researcher would immediately distrust.

    Fix direction (not yet implemented): before attempting selector
    resolution, confirm lr or the current pc corresponds to a call
    into a known objc_msgSend-family stub address (objc_msgSend,
    objc_msgSend_stret, objc_msgSendSuper2, etc.) rather than trusting
    register value shape alone. This is a different, more fundamental
    bug than 3's address-range heuristic -- that one has wrong
    thresholds; this one has no verification step at all before
    treating arbitrary register contents as a selector pointer.

    Priority: medium-high. Silent misattribution (not just silent
    failure) is a real trust problem for a tool whose core value
    proposition is deterministic ground truth -- see
    docs/target-independence.md and the "MACE is ground truth"
    philosophy referenced there.

4. Inline string detection
   Any valid pointer -> attempt string read -> display if printable
   Max 64 chars, truncated with ellipsis
   Covers NSString, C strings, Swift strings

5. Branch prediction at current pc
   Show likely next instruction path for conditional branches
   cbz/cbnz/b.eq/b.ne etc -> show both paths, highlight taken
   Makes "what happens next" answerable without stepping

### Reference implementations:
- GEF (hugsy/gef) - original inspiration, GDB
- LLEF (foundryzero/llef, 489 stars) - GEF for LLDB, x86/ARM64/Go
  Borrow: configurable rebase_offset for Ghidra/IDA compatibility

### LLEF coexistence note:
LLEF and MACE are competing stop hooks - do NOT run simultaneously.
LLEF = general RE/VR. MACE = mobile AArch64 specialization.
Study LLEF's UI design, do not combine.

### LIEF integration (lief.re):
Binary parsing backend for MACE context enrichment.
pip install lief - works in LLDB Python environment.
Use cases:
- Automatic __text range for caller filter (replaces image dump sections)
- Stub address resolution -> symbol names
- ObjC selrefs parsing -> passive annotation without EvaluateExpression
- Flutter libapp.so ELF parsing for Dart snapshot offsets
New module: mace/core/binary_context.py

### AI layer is the killer differentiator (v3):
Panel improvements make v1 useful standalone.
AI annotation makes MACE a different class of tool entirely:
"You are stopped inside ISS ptrace check, x0=0x1f = PT_DENY_ATTACH,
patch with reg write x8 0 at offset +1320"
That answer cannot come from panel formatting - only from AI reasoning
over deterministic register state. That is MACE's unique position.

## MachOSwiftSection — Swift Type Annotation Solution
Source: github.com/MxIris-Reverse-Engineering/MachOSwiftSection (284 stars)
Discovered: Aug 2026 — solves Swift type annotation gap from MACESecurityTest session

### Problem solved:
object_getClassName() fails on pure Swift types (ISS, SwiftUI).
MACE annotation returns empty for Swift receivers.
MachOSwiftSection provides Swift-native type resolution.

### Install:
    brew install swift-section

### Capabilities relevant to MACE:

1. SwiftDump — type name resolution
   Resolves x0 pointer to Swift type name
   e.g. x0 = 0x104a714e0 -> IOSSecuritySuite.DebuggerChecker
   Swift equivalent of object_getClassName()

2. SwiftInspection MetadataReader
   Demangles Swift types and symbols against Mach-O at runtime
   Resolves mangled names in annotation panel

3. Static field offsets (--emit-field-offsets)
   Struct member layout computed statically
   When MACE stops inside Swift struct:
   offset +0x08 = ret_errorp, offset +0x10 = ret_pathp
   Makes register interpretation dramatically more useful

4. Protocol conformance mapping
   ISS type hierarchy — which types conform to which protocols
   Enriches annotation with protocol context

### CLI usage before MACE session:
    swift-section dump --architecture arm64 /path/to/binary
    swift-section interface --architecture arm64 /path/to/binary

### MACE integration:
New module: mace/core/swift_context.py
Parse swift-section output at session start
Feed type names into annotation layer for Swift receivers
Complement to LIEF (binary structure) + MachOSwiftSection (Swift semantics)

### Note:
Repo has MCP directory — watch for their MCP server implementation.
May provide Swift binary analysis tools directly as MCP tools.
Coordinate with MACE MCP server design to avoid overlap.

### Relationship to other static tools:
    LIEF              -> binary structure (ELF/Mach-O sections, imports)
    MachOSwiftSection -> Swift semantics (types, fields, protocols)
    Hopper            -> quick iOS disassembly, Swift demangling UI
    JEB               -> deep Android native + iOS ARM64 decompilation
    Together: complete static context feeding MACE dynamic observation

## Dart/Flutter AArch64 Specifics (from Apvrille BlackAlps 2023)
- Object pool register tracking — identify and dereference Dart object pool pointer
  (strings/constants not in __cstring, stored in pool accessed via dedicated register)
- Integer tag awareness — Dart small integers have LSB tag, displayed value = actual * 2
  (MACE must strip tag before showing decimal annotation)
- Stack-based argument convention — Dart pushes args to stack not x0-x7
  (MACE argument annotation must read sp offsets for Dart functions)
- Blutter integration provides addresses for breakpoints without exported symbols
  (bridges the Frida gap Apvrille identifies at BlackAlps 2023)

## Dart ARM64 Register Map (from Worawit Wangwarunyoo, HITB 2023)
Source: Blutter author's primary presentation
From dart/runtime/vm/constants_arm64.h

When MACE context panel shows Flutter/Dart target:
- x15 (R15) → Dart VM Stack Pointer (SPREG), NOT general register
- x16 (R16) → TMP scratch
- x17 (R17) → TMP2 scratch  
- x21 (R21) → Dispatch Table Register
- x22 (R22) → NULL_REG (always caches NullObject())
- x24 (R24) → CODE_REG
- x26 (R26) → THR (current Dart Thread)
- x27 (R27) → PP (Object Pool Pointer)
- x28 (R28) → HEAP_BITS
- x4  (R4)  → ARGS_DESC_REG (Arguments Descriptor)
- x5  (R5)  → IC_DATA_REG

Calling convention:
- Arguments passed on Dart stack (R15), NOT in x0-x7
- Named parameters: R4 = Arguments Descriptor array
- Dart stubs: use specific registers per ABI struct in constants_arm64.h

iOS note: Pointer compression NOT enabled (requires entitlement)
- Full 64-bit object pointers on palera1n iPad
- Simplifies Dart object inspection via MACE memory reads

MACE implementation needed:
- Dart mode detection (check if pc in libapp.so range)
- Conditional register annotation switching to Dart names
- Object pool dereference for string/constant lookup via x27

## r2SMT — SMT-Assisted Opaque Predicate Deobfuscator
Source: github.com/seifreed/r2SMT (Marc Rivero/@seifreed, r2con2025 author)
Same author as r2morph

SMT-assisted opaque predicate deobfuscator for radare2.
Uses Z3/CVC5/Bitwuzla to mathematically prove whether conditional branches
can go both ways. Proven single-direction branches = opaque predicates.

AArch64 supported (multi-arch lifters: x86, x86_64, AArch64, AArch32/Thumb)

Pipeline with MACE:
  r2morph  -> adds opaque predicates as obfuscation
  r2SMT    -> proves and removes opaque predicates statically
  MACE     -> observes real execution below the obfuscation

Verdicts:
  AlwaysTrue / AlwaysFalse -> opaque predicate, proven obfuscation
  BothPossible             -> genuine branch, MACE observes runtime state

Install: cargo build --release (requires Rust 1.85+, radare2 6.1+, CMake)

Status: Very early (2 stars, 12 commits) but architecturally sound.
Complements r2morph + MACE as complete obfuscation/deobfuscation/analysis stack.

## mace_swift_load — device-path auto-resolution [RESOLVED 2026-08-23]
Source: LocalAuthTest MACE-native validation session, 2026-08-22
Resolved: same target, 2026-08-23

Original problem: _resolve_local_path() in swift_context.py attempted to
resolve device-only paths via SBModule.GetFileSpec() on the target's
loaded modules. This did NOT work in practice for app-owned dylibs
pulled over a debugserver connection — GetFileSpec() returns the same
remote path (e.g. /private/var/containers/...), not a local cached
copy. (It does appear to work for system frameworks, which LLDB
caches under ~/Library/Developer/Xcode/iOS DeviceSupport/.../Symbols/.)

Fix implemented: auto-detect the matching local DerivedData path by
binary basename, picking the most-recently-modified match if several
exist (this was "option 3" of three approaches originally considered
here; a remote SBPlatform.GetFile() pull and an automatic scp fallback
were the other two, neither pursued since this was sufficient). When the
module-cache lookup misses, _resolve_local_path() now also searches
~/Library/Developer/Xcode/DerivedData recursively for a file matching
the binary's basename. SwiftContext.resolved_path records which path was
actually used, and mace_swift_load surfaces it explicitly:

  [MACE] Swift context loaded: 6 types from MACELocalAuthTest.debug.dylib
  [MACE]   note: device path not found locally — auto-resolved to
           /Users/.../DerivedData/MACELocalAuthTest-.../MACELocalAuthTest.debug.dylib

Validated live: mace_swift_load called with the raw device path
(/private/var/containers/...) resolved automatically with zero manual
path-hunting, on the MACELocalAuthTest unstripped build.

Known limitation carried forward: mtime-based selection is a
heuristic, not a guarantee — a stale build for a different scheme
touched more recently could still win over the actually-running
build. Worth revisiting if this ever produces a wrong-type-resolved
mismatch in practice. The remote-file-pull and scp approaches remain
undone and lower priority now that the DerivedData search removes
the actual day-to-day friction.


## stop_hook.py — split into multiple modules once registration
## pattern is validated
Source: session discussion, 2026-08-28, after adding mace_grep/
mace_search brought the file to 406 lines / 7 command classes

Not urgent yet — 406 lines is still genuinely readable (one class per
command, consistent docstrings), and the growth trajectory (roughly
+100-150 lines per session of active feature work) is a "soon," not
a "now" problem. Flagging so it doesn't just keep growing by default
without a deliberate decision.

The real blocker isn't file length -- it's an untested assumption.
Every command is currently registered as
`command script add -c stop_hook.ClassName`, which only resolves
because LLDB matches it against the flat `stop_hook` module name
created by however the user's personal ~/.lldbinit does
`command script import` on this specific file. This was a deliberate
choice made early (see MACESwiftLoad's original addition) specifically
to avoid gambling on whether `-c mace.lldb.some_new_file.ClassName`
-style package-qualified resolution actually works for a genuinely
separate module -- never tested live.

Before attempting a real split: run one small, throwaway experiment
first -- register a dummy command from a genuinely separate file
using the package-qualified path, confirm it resolves correctly on
real hardware, before committing to restructuring the real commands.
Splitting blind risks breaking every command at once if the
assumption turns out wrong.

Four natural groupings already visible in the current single-file
structure, ready to become their own modules once the registration
pattern is confirmed safe:
- Core panel toggle: MACEStopHook, mace_on, mace_off
- Swift context loading: MACESwiftLoad
- Patching + audit: MACEPatch, MACEPatchHistory
- Introspection/query: MACEGrep, MACESearch

Also worth noting: v3's MCP server work will need its own dedicated
module (e.g. mace/mcp/server.py) regardless of what's decided here --
so this file-organization question returns for real soon either way,
just not urgently today.


## mace_grep bugs found during iGoat-Swift investigation (2026-08-29)
Source: igoat_investigation_notes.md

Both found live, mid-investigation. Neither blocked the session (both
had usable workarounds found in the moment) but both are real,
reproducible parsing bugs worth fixing properly.

### Bug A -- `-i` flag doesn't exist, silently corrupts argument parsing
mace_grep is already always case-insensitive by design (re.IGNORECASE
baked into the pattern compile) -- there was never a flag to add.
Passing one anyway wasn't rejected with a usage error; instead it got
consumed as if it were the search pattern itself, shifting the rest of
the command incorrectly:

  mace_grep -i "jailbreak" "image dump symtab iGoat-Swift"
  → [MACE] Command failed: error: 'jailbreak' is not a valid command.

Fix direction: parts[0].split(None, 1) currently assumes the first
whitespace-separated token is always the pattern. Should either
explicitly reject/ignore a leading "-i" with a clear message ("mace_grep
is already case-insensitive, no -i needed"), or more robustly, stop
assuming position 0 is always the pattern and use a real flag parser.

### Bug B -- pattern argument isn't quote/escape-stripped, only the inner command is
inner_command has `.strip().strip('"').strip("'")` applied; pattern
does not. Any pattern that legitimately needs quoting (spaces, regex
metacharacters) carries the literal quote/escape characters into the
compiled regex, guaranteeing zero matches even when real matches
exist:

  mace_grep "OBJC_CLASS_\$_" "image dump symtab iGoat-Swift"
  → [MACE] No matches for '"OBJC_CLASS_\$_"' in 9475 lines of output.

Note the literal quotes and backslash still present in the error
message's echoed pattern -- confirms they were never stripped before
regex compilation. Fix direction: apply the same
.strip().strip('"').strip("'") normalization to the pattern argument
that inner_command already gets, before regex compilation.

Workaround used this session for both: avoid needing quotes/escapes
in the pattern at all where possible (e.g. "OBJC_CLASS" instead of
"OBJC_CLASS_\$_" -- $ isn't needed for a substring match here).

UPDATE 2026-08-30 (syscall_annotation_notes.md): Bug B recurred live
during the DVIA-v2 syscall-annotation session --
mace_grep "write|atomically|documentsDirectory|dataFilePath|NSDictionary"
matched only 1 of 770 lines (the quoted first/last alternatives were
corrupted the same way). Confirms the bug is real and reproducible,
not a one-off; still not fixed. Same workaround applied (dropped the
quotes, pattern had no spaces so this was safe).

## Breakpoint insertion failure -- Foundation fileExistsAtPath:, iGoat-Swift session (2026-08-29)
Source: igoat_investigation_notes.md

  br set -a 0x181872f44
  → warning: failed to set breakpoint site at 0x181872f44 for
    breakpoint 2.1: error: 9 sending the breakpoint request

lldb still created the breakpoint object and reported a clean
"Breakpoint 2: address = ..." despite the warning -- easy to miss
that the underlying debugserver write likely failed. Confirmed via
non-fire: triggered the code path that should have hit this address
(Foundation's -[NSFileManager fileExistsAtPath:], called by iGoat's
Cydia-path check) and the breakpoint never fired, while the app's
behavior was otherwise consistent with the check having run normally.

Not yet root-caused -- no other breakpoint this project has produced
this warning. Retroactively raises an open question about an earlier
breakpoint in the same session (libsystem_kernel.dylib's __ptrace,
no warning shown) that also never fired across several attempts --
absence of the warning is a real point in its favor but not
independent confirmation it actually worked. Worth watching for
recurrence of "error: 9 sending the breakpoint request" specifically
-- if it shows up again, especially against shared-cache library
addresses, treat any breakpoint set the same session with more
suspicion even without an explicit warning.

UPDATE 2026-08-30 (syscall_annotation_notes.md): the open question
above is now resolved differently than expected. A live session
extensively re-tested shared-cache breakpoints (four separate
libsystem_kernel.dylib symbols, both software and hardware, against
confirmed real code execution) and initially concluded shared-cache
placement itself was the common factor in every failure. That theory
was then DISPROVEN the same session: a breakpoint on
libsystem_kernel.dylib's mach_msg2_trap (the exact same shared-cache
image as every failure) fired immediately, first attempt. The real,
better-supported explanation across all of today's evidence: every
failure was either a genuinely one-shot call, or a call whose
containing code path was confirmed (via thread list) to never
actually execute on that run -- not shared-cache placement, which is
demonstrably fine. This specific Foundation/error-9 instance remains
unexplained on its own terms, but the broader "shared cache
breakpoints are unreliable" generalization it seemed to support does
not hold.

## Two new display bugs found via a genuinely new thread (2026-08-30)
Source: syscall_annotation_notes.md

Found while single-stepping toward DVIA-v2's real plist write. A
normal GCD worker-pool thread got created mid-session
(start_wqthread) -- routine, unrelated to the target being debugged
-- and MACE's panel rendered for that stop too, surfacing two real,
previously-unseen bugs.

### Bug A -- malformed breakpoint ID on this thread's stop
Rendered as "breakpoint 18446744073709551612.1" -- almost certainly
a -4 value misread as unsigned (2^64 - 4 = 18446744073709551612).
Likely _get_breakpoint_id()'s GetStopReasonDataAtIndex() returning a
signed value not being reinterpreted correctly -- similar in spirit
to (but a distinct bug from) the signed-x16 handling added for
syscall annotation the same session. Not yet fixed.

### Bug B -- nonsensical ASLR offset on a stop outside the main module
Shown as slide=0x...ac000 offset=0x1fbaf1aa8, which doesn't
correspond to pc - slide for this stop at all. Root cause:
_compute_aslr_slide() always uses the MAIN app module's base (module
index 0) regardless of which image the actual stop is in --
meaningless once a stop happens inside a different image
(libsystem_pthread.dylib here) on another thread. Fix direction:
either compute slide per-image (resolve which module actually
contains pc, use that module's base) or suppress the offset field
entirely when pc falls outside the main module's known range, rather
than showing a number that looks real but isn't. Not yet fixed.

Neither bug affects the objc or syscall annotation features
themselves -- both are display/formatting issues in the stop-banner
line.


## Register panel — show signed reinterpretation for negative-looking values (2026-08-30)
Source: session discussion, reviewing a real DVIA-v2/mach_msg2_trap
panel screenshot

The general register panel (render_registers() in context_panel.py)
always shows the decimal column as a raw unsigned interpretation, even
when the top bit is set. Concretely, in the reviewed screenshot:

  x16    0xfffffffffffffd1  # 18446744073709551569u

That's the exact same register value _annotate_syscall() (added this
session) already correctly reinterprets as signed -47 to identify a
Mach trap -- the general panel just doesn't apply that same logic to
the decimal column it shows for every register, so a human reading
the raw panel sees a confusing 20-digit number where a signed value
would immediately read as "this is probably meaningful as -47, likely
a small negative number, not a huge positive one."

Fix direction: in _format_register_line() / render_registers(), when
the top bit (bit 63) is set, show the signed reinterpretation
alongside (or instead of) the unsigned one -- e.g.
"# -47i (18446744073709551569u)" or similar. Reuse the exact
sign-reinterpretation logic already written and tested for
_annotate_syscall() (raw - (1 << 64) if raw >= (1 << 63) else raw)
rather than re-deriving it.

Distinct from, but related to, the memory-region-labeling item above
(Context Panel v2, item 3) -- that one is about giving ADDRESS-shaped
values (x0, x1, x3, x5 in the same screenshot -- genuinely large
positive numbers, stack/heap pointers) a real region label instead of
a raw decimal; this one is specifically about correctly signed
NEGATIVE-looking values (x16 here) being shown as if they were huge
positive numbers when they're not. Both are real, separate
readability gaps in the same panel, surfaced by the same screenshot.

UPDATE 2026-09-04: Implemented. Added ContextSnapshot.as_signed()
(same formula as _annotate_syscall()) and wired it into
_format_register_line()/render_registers(), scoped to x0-x28 only —
never fp/lr/sp/pc, which are unambiguously addresses by ABI
definition and should never be shown as signed. Display format:
append "(-Ni)" after the existing "# {decimal}u" rather than
replacing it, so every register line still starts the same way and
the signed hint is purely additive when relevant. 6 mock tests cover
the exact live case (x16=-47), a second independent negative value
(not just the one hardcoded example), small-positive and
address-shaped registers correctly showing no hint, and fp/lr/sp/pc
correctly never showing one even with the top bit artificially set.
Committed (267e8b5). Low-risk relative to prior annotation fixes —
pure post-processing of already-captured register values, no new
LLDB API surface touched — so treated as done on mock-test confidence
alone rather than requiring a dedicated live-hardware session, unlike
the objc/syscall annotation work which genuinely depended on live
SBFrame/SBTarget behavior that couldn't be fully predicted.

## lldb-server platform mode spawns a dynamic, unforwarded gdbserver child on attach (2026-09-06)
Source: android_first_connection_notes.md

First-ever Android connection session. Confirmed directly via
--log-file/--log-channels logging (lldb-server is silent by default in
BOTH platform and gdbserver modes -- worth always enabling logging
going forward, not just when troubleshooting):

  < 21> read packet: $qLaunchGDBServer;
  < 25> send packet: $pid:20438;port:34313;

Platform mode's `process attach` doesn't debug directly over the
platform connection -- it spawns a brand-new, separate gdbserver child
process on an unpredictable, dynamically-assigned port for the actual
debug session. Only the platform port (1234) was ever forwarded via
adb forward; the real debugging channel MACE's stop-hook/breakpoint
code depends on was running on a never-forwarded port the entire
session. This plausibly explains a whole day's worth of "breakpoint
resolves, some threads show trace, but no panel ever renders"
mysteries -- not a MACE Python logic bug at all.

Fix direction, not yet implemented: switch from platform mode to
plain gdbserver mode with a direct --attach=<pid>, the same shape as
debugserver --attach used successfully every time on iOS this whole
project -- a fixed, known, single port for the whole session, no
dynamic child spawning, genuinely scriptable. Confirm exact syntax
fresh next session (`lldb-server gdbserver --help`) rather than
assume from today's platform-mode syntax.

UPDATE 2026-09-06 (research log, s11research.com/posts/debugging-
android-with-lldb/, a real RECON conference speaker, credible source):
independent confirmation our connection setup itself was correct --
their platform connect output (Triple aarch64-unknown-linux-android,
OS Version N, Connected: yes) is line-for-line identical in shape to
what this session got. But their actual workflow suggests a more
precise hypothesis than "abandon platform mode entirely": they never
use `process attach` to an already-running PID at all -- they use
`target create <path>` + `process launch --stop-at-entry -- <args>`,
launching a FRESH process directly through the platform connection,
never attaching to something already running. This raises a real,
untested possibility: the dynamic, unforwarded child-port behavior
found in the logs may be specifically an ATTACH-mode artifact, not a
platform-mode-wide one -- a fresh launch may let the platform
connection create and own the child process from its first
instruction, without needing the same "find and attach to an
arbitrary existing PID" handshake that spawned the separate
gdbserver child on port 34313 during our attach attempt.

Not confirmed either way -- their writeup doesn't show server-side
logging, so whether `process launch` also spawns a similar dynamic
port is genuinely unknown, not ruled out. Revised plan for next
session: try `target create` + `process launch` on a disposable
target FIRST, with --log-file/--log-channels still enabled so the
logs can directly confirm or rule out a second dynamic port under
launch too -- only fall back to switching to plain gdbserver mode
(the original fix direction above) if the same behavior recurs.

Also worth noting: their right-hand-panel setup (disassembly,
registers, stack, all live-updating per stop) is via a real, working
GEF-style lldb overlay called "voltron" (github.com/snare/voltron) --
genuine, independent prior art for exactly the kind of panel MACE
already builds, though MACE's own panel is annotation-aware (objc/
Swift/syscall context) rather than a raw register/disassembly dump,
a meaningfully different and more purposeful design, not something
to adopt directly.

UPDATE 2026-09-06 (research log, JetBrains YouTrack article
SUPPORT-A-4012, "Setup Remote-debugging Android native code with
RustRover + lldb-server (gdbserver mode) Standalone" -- a real,
detailed, current guide with an explicit troubleshooting section):
DECISIVE. This guide states the root cause in plain terms, directly
confirming the fix direction above rather than just suggesting it:

  "Also occurs if LLDB is started in platform mode
  (lldb-server platform --listen ...) but uses [a client's] gdbserver
  mode (process connect) -> protocol mismatch. Always use:
  lldb-server gdbserver :5039 ... and connect://localhost:5039 on
  the host."

Three independent sources now agree: our own log evidence
(dynamic, unforwarded child port under platform mode), s11research's
writeup (never uses process attach, always launches fresh via
target create + process launch), and this JetBrains guide (explicit,
documented protocol mismatch between platform and gdbserver modes).
No longer a hypothesis -- platform mode is confirmed the wrong choice
for actual debug sessions; it is fine for the read-only discovery
things it's designed for (process list, module info), but the real
debugging connection needs plain gdbserver mode.

SUPERSEDED 2026-09-13 (research prompted by an outside friend review
of the repo): this specific conclusion was wrong, and the record is
being corrected rather than erased, per this project's own established
practice. The real, live-verified fix (see the platform-mode-
resolution entry further down) is the opposite: lldb-server PLATFORM
mode, paired with a setting never tried at the time this entry was
written (`settings set platform.plugin.remote-android.package-name
<pkg>`, set before connecting), is what actually populates a real,
Android-aware module model and lets named breakpoints resolve. The
JetBrains guide's own "protocol mismatch" observation was real for
ITS specific setup, but doesn't generalize the way this entry assumed
-- worth remembering that a real, credible external source's own
finding can still be scoped more narrowly than it reads at first.

Working syntax confirmed directly from this guide (adjust host/port
for our own setup, verify against `lldb-server gdbserver --help`
rather than copy blindly):

  adb forward tcp:5039 tcp:5039
  lldb-server gdbserver :5039 <path-to-binary>
  (lldb) platform select remote-android
  (lldb) process connect connect://localhost:5039

Bare port (no `*:` prefix), and the target is a BINARY PATH launched
directly by lldb-server itself -- not a PID being attached to --
matching s11research's launch-based approach exactly, not our
attach-based one. Revised plan for next session: launch a disposable
target fresh via this exact gdbserver+launch pattern; only fall back
to investigating --attach=<pid> support specifically if launching a
fresh process turns out to be impractical for the actual validation
target chosen.

One real, separate finding from this same guide, likely NOT our
actual root cause but worth knowing: a documented SELinux/app-sandbox
failure mode ("Operation not permitted" opening a listening socket)
specific to running lldb-server via `run-as <package>` (an app's own
restricted sandbox user). We ran everything as root via Magisk su the
entire session -- a meaningfully more privileged context than run-as
ever grants -- so this specific blocker almost certainly doesn't
apply to us, but worth remembering if a future target ever needs
`run-as`-scoped debugging instead of root.

UPDATE 2026-09-11 (research log, android_debuggable_patch_notes.md):
DEFINITIVELY RESOLVED, and worth correcting the written record
plainly rather than let a wrong theory stand (same Rule 9 discipline
as the yuvalino case study). Built a real, from-scratch APK decompile/
patch/rebuild/sign/install pipeline and tested a real app (Frida-Labs
Challenge 0x1) patched to android:debuggable="true" -- gdbserver
--attach succeeded cleanly, first try, full 22-thread enumeration,
with lldb-server itself printing an explicit "Attached to process
<pid>..." confirmation never seen in any deskclock attempt.

Critically, this ran with SELinux in Enforcing mode throughout (the
earlier setenforce 0 from the prior session didn't survive the device
reboot, and was never reapplied) -- and the attach still succeeded.
That means the SELinux-permissive theory logged in the earlier UPDATE
above is very likely a RED HERRING, not the real fix -- the ONLY
variable that actually differed between every failing attempt
(deskclock, non-debuggable, tried both Enforcing and Permissive) and
this succeeding one (Frida-Labs 0x1, patched to debuggable, Enforcing
throughout) was the manifest debuggable flag itself. That flag is
confirmed as the true, sole gate on gdbserver --attach against real
app processes -- not SELinux mode, and (per the same session) not
platform mode vs gdbserver mode either, since the underlying gdbserver
mechanism itself was proven correct once the real variable (debuggable
flag) was controlled for.

Real, reusable pipeline built from this, available for every future
Android target: apktool decode -> sed the manifest -> apktool build
-> apksigner sign (reusable keystore at
MobileBinaryTargets/shared/mace-debug.keystore) -> apksigner verify
-> adb install. Full details, including a bonus finding (MASTG
UnCrackable L1 Android has its own runtime debuggable-flag self-check
that self-exits, a real anti-debug challenge worth returning to once
mace_patch-based Android bypass work begins) in
android_debuggable_patch_notes.md.

## Shared ART-runtime syscall primitives are a much riskier breakpoint target than the equivalent choice on a native daemon (2026-09-11)
Source: android_debuggable_patch_notes.md

Real correction to a heuristic that worked well once and then failed
badly the next time it was applied. "Pick the syscall address with
the most threads converged on it" was the right call for netd (a
native daemon) on the first Android session -- froze cleanly, real
multithreaded panel rendering validated, no ANR. Applying the exact
same heuristic to an ART-managed app process (Frida-Labs Challenge
0x1) produced a real ANR almost immediately after continue, even with
no premature detach involved.

Root cause: the busiest shared syscall site in a managed-runtime
process is disproportionately likely to be the runtime's OWN internal
plumbing, not incidental activity. The specific address chosen
(0x710b768860) was hit by HeapTaskDaemon, FinalizerDaemon,
ReferenceQueueDaemon, Profile Saver, Jit thread pool, and several
hwuiTask/mali- threads -- strongly suggesting a core ART
synchronization primitive (very likely a futex wait) that the
runtime's own scheduler/GC/JIT machinery depends on continuously.
Freezing it can stall the whole app's runtime almost immediately,
unlike freezing the equivalent syscall on a native daemon, where
background threads pausing briefly was well-tolerated (netd handled
this fine both times it was tested).

Fix direction for future ART-managed-app sessions: target a
breakpoint on the APP'S OWN code path specifically (reached via real
UI interaction -- e.g. tapping a button the app's own MainActivity
handles), not a shared syscall site with many background daemon
threads converged on it. The "most threads = most reliable target"
heuristic should be treated as native-process-specific, not a general
MACE rule -- worth a note in the debugging playbook distinguishing
the two cases explicitly.

## lldb has never had a populated module list on Android via gdbserver --attach (2026-09-12)
Source: android_module_resolution_notes.md

Real root cause found for something silently true and visible in
EVERY Android connection summary this whole project, going back to
the very first netd attach: "Target 0: (No executable module.)"
Never investigated directly until today, because every prior
successful breakpoint used a raw address (-a 0x...), which needs no
module/symbol resolution at all. Confirmed directly today: `image
list` returns "error: the target has no associated executable
images", and a named-symbol breakpoint (`breakpoint set -n strcmp`)
correctly resolves to nothing ("no locations (pending)") as a direct
consequence.

Real, meaningful implication: NAMED-symbol breakpoints cannot work on
Android via the current gdbserver --attach workflow at all, regardless
of signal handling or target/process ordering -- only raw address
breakpoints have ever actually worked. A real limitation relative to
iOS, where debugserver's attach always populates a real module list
automatically (every iOS Target line this whole project has shown a
real module name).

Attempted fixes, none fully resolved it: `target create <local pulled
app_process64>` issued AFTER an existing process connect actively
DISCONNECTS the session rather than augmenting it (real, concrete
lesson on its own -- target create and an existing live connection
don't compose the way one might expect). Reordering to target create
FIRST, then connecting, left `image list` showing only the single
app_process64 image at load address 0x0 -- never tied to the live
process's real, relocated memory layout, and libc.so never appeared.
`process attach -p <pid>` as a follow-up triggered an ANR before
anything could be checked further.

Well-reasoned hypothesis for next time, not yet tested: every prior
WORKING example of named-symbol resolution this whole project has
found (s11research's blog, JetBrains' RustRover guide) used `target
create` + `process LAUNCH`, never `process attach` to an already-
running process. Launching lets lldb observe the process from its
very first instruction and track the dynamic linker's incremental
library-load sequence as it happens -- exactly how lldb normally
discovers modules. Attaching to an already-fully-loaded process gives
it no mechanism to retroactively backfill that history. This may be
fundamentally an attach-vs-launch limitation of gdbserver mode on
Android, not something fixable by ordering/signal tweaks alone --
worth testing directly against a genuinely launchable target (a
standalone native binary, or the custom EEA-on-Android idea already
discussed) before continuing to fight attach-based resolution for a
Zygote-forked app process specifically.

UPDATE 2026-09-13 (research prompted by an outside friend review):
this hypothesis was correctly SCOPED (it named gdbserver mode
specifically, not attach on Android generally) but the underlying
cause was a real, natural confound, not attach-vs-launch as its own
dimension. Every attach attempt up to this point happened to be under
gdbserver mode; every launch success also happened to be under
gdbserver mode -- attach specifically under PLATFORM mode was never
tested until the very next session. Once it was: `process attach
--pid <PID>` after a normal `am start` launch, through the
remote-android platform plugin with the package-name setting,
produced a fully populated module model and working named breakpoints
-- no launch involved at all. The real differentiator was always the
Android-aware platform connection and module reconstruction, not
attach versus launch. See the platform-mode-resolution entry further
down for the full, live-verified result.

## Android 16 requires 16KB memory page alignment for native libraries (2026-09-12)
Source: android_module_resolution_notes.md

Real, current Android 16 compatibility finding, surfaced incidentally
while installing Frida-Labs Challenge 0x8: a dialog reading "This app
isn't 16 kb compatible. APK and ELF alignment checks failed" for
libfrida0x8.so and liblog.so -- both built before this requirement
existed. Dismissible, did not block the app from running, but a real,
current thing worth knowing: any older native-code Android app or
crackme predating this requirement may show the same warning when
tested against the Pixel 10a / Android 16 target. Not investigated
further today; worth remembering as a possible source of confusion
(a dismissible warning, not a real failure) if it shows up again on a
future target.

## Named-symbol breakpoint resolution CAN work on Android -- but not yet reliably (2026-09-13)
Source: android_named_symbol_reliability_notes.md

Major update to the module-resolution entry above. Using a plain,
standalone native binary (the same EEA/Google-CTF-2020 flag-checker
logic, cross-compiled for Android ARM64 directly) to isolate the
launch-vs-attach question cleanly, the exact missing combination was
found: `target create <local-binary>` BEFORE connecting, paired with
a genuine LAUNCH (not attach). This produced a real, populated module
list (a real load address, [vdso] visible) and a named-symbol
breakpoint (`breakpoint set -n validate`) that resolved COMPLETELY,
with full source-line correlation (`flag_checker.c:53:25`) -- the
first confirmed instance of this working on Android this entire
project.

HOWEVER: this exact result could not be reproduced afterward in the
same session, across multiple rebuilds (dynamic PIE, static-pie, and
even the identical original -static binary rebuilt fresh) and a
deliberate 10+ second delay between server launch and connect.
Theories tested and ruled out: simple race condition (long delay
didn't help), background app interference (force-stopped EEA
entirely, no change), device-level degradation (adb devices/echo
hello both clean and fast, unlike the session that needed a reboot).
The actual cause of the shift from "worked" to "consistently fails"
within one otherwise-healthy session remains genuinely unknown.

Real, useful side-finding from the same investigation: the "multiple
lldb-server PIDs" pattern seen constantly this whole project has a
clean, non-alarming explanation -- `pgrep -f` matches the full command
line, and since lldb-server is invoked via `su -c 'lldb-server ...'`,
the su wrapper's own command line contains the literal string
"lldb-server" too. Two pgrep matches, one real process, not a genuine
double-fork.

Status: the core mechanism is proven to work, once. Reliability is
not solved. Next session should NOT assume this is fixed -- treat
every attempt as needing fresh verification until a real, reproducible
trigger for the failure mode is found.

UPDATE 2026-09-13 (same day, afternoon session): a real, concrete fix
found and LIVE-VERIFIED against the real EEA app, not just theorized.
CB brought an independent troubleshooting document describing a
different working architecture; verified its claims ourselves rather
than accepting them secondhand. Two previously-uncontrolled variables
identified: (1) every session this entire project used Apple's
bundled /usr/bin/lldb, never a separately-installed Homebrew build;
(2) every attempt against a real app used gdbserver mode, never
lldb-server PLATFORM mode with the setting
`settings set platform.plugin.remote-android.package-name <pkg>` set
BEFORE connecting. Using Homebrew lldb + platform mode + the package-
name setting + `process attach --pid` after a normal `am start`
launch, produced a real, rich module list (428+ modules, including
libeea.so at a real load address) and a named-symbol breakpoint
(`breakpoint set -n validate -s libeea.so`) that fired cleanly on the
real app's main thread with real, live argument data visible
(`input="yuhygg"`). See android_platform_mode_resolution_notes.md for
the full verification. Not yet re-tested for reliability across
multiple attempts -- treat as a real, working fix for THIS specific
problem, not a claim that every open Android question is resolved.

## Repeated attach+continue on a real ART app process can trigger unrelated background-thread crashes (2026-09-13)
Source: android_named_symbol_reliability_notes.md

Separate, new finding from testing a correctly-computed address
breakpoint (via /proc/pid/maps + llvm-nm/llvm-readelf, accounting for
the executable PT_LOAD segment's own file offset) against the real EEA
app. Continuing past the breakpoint did not hit the intended target --
instead, twice in a row, on separate attempts, an unrelated SIGSEGV
crashed a DIFFERENT background thread each time (SurfaceSyncGroup,
then AsyncTask #1), both with the IDENTICAL instruction signature
(`ldr x21, [x21]`, fault address 0x0) and an identical trailing
mov/movk sequence.

This is distinct from Rule 12's ART-runtime-primitive ANR risk (a
freeze from choosing the wrong breakpoint target) -- this is a genuine
CRASH, in a thread unrelated to the actual breakpoint address, that
appears to be a side effect of repeatedly attaching to and continuing
a real, busy, multi-threaded ART app process. Root cause not
understood; worth treating as a real, separate risk category for
Android app-process debugging sessions, alongside the already-known
ANR risk.

## The real architectural difference between iOS and Android connections: who performs the attach (2026-09-14)
Source: research conversation, cross-checked against docs/ios-setup.md

CB's own question surfaced this precisely: "one difference between
iOS and Android is that in Android we connect platform whereas in
iOS we ran process connect." Checked against the actual iOS
workflow on file (docs/ios-setup.md) rather than trust either memory
-- the real distinction is narrower and more interesting than that
framing suggests. BOTH platforms select a platform first
(`platform select remote-ios` / `remote-android`). The real
difference is one step later, and it's about WHO performs the attach,
not whether platform mode is used at all.

iOS: `debugserver 0.0.0.0:1234 --attach=<PID>` on the device -- the
server itself does the attaching, in the launch command. lldb's
`process connect` just joins that already-established session
directly.

Android's actual working recipe (2026-09-13): `lldb-server platform
--listen ... --server` opens a listening/discovery layer only -- it
attaches nothing by itself. `platform connect` joins that layer, then
a SEPARATE step, `process attach --pid <PID>`, performs the actual
attach -- done by lldb's own remote-android platform plugin client-
side, not by the on-device server.

Real, worth-remembering explanation for WHY Android specifically
needed this recipe: Android's process model (Zygote forking, ART,
JNI, dozens of shared libraries per process) needs lldb's own richer,
platform-aware attach logic actively reconstructing a real module
model. A bare "connect to whatever's already attached" -- all
`process connect` ever does -- was never going to be enough for that.
iOS's simpler, single-Mach-O-binary-per-process model doesn't need
that extra reconstruction layer; a plain server-side attach already
hands lldb everything it needs directly.

General principle for any future platform work: when debugging a new
target's connection model, "who actually performs the attach --
server or client platform plugin" is a more useful first question
than "which specific commands does the working example use." See
debugging playbook Rule 15.
