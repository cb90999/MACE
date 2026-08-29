# MACE Backlog

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
- fatalsec renef — SVC direct syscall, libantifrida.so
- xairy pixel-kgdb — Android kernel debugging, PAC backtrace corruption
- IOCCC 2025 uellenberg — compiler obfuscation techniques
- Garuda Defender APK — anti-debug detection analysis (Thursday)
- 8ksec OAAE — ARM exploitation cert, MACE as study environment

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
   (Aug 2026) as a target/device-specific heuristic living in core code
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
