# MACE Android Setup Guide

## Tested Configuration
- Pixel 10a (arm64-v8a, Android 16 / API 36, Magisk root)
- M5 MacBook Pro (LLDB + MACE)

## Prerequisites
- Magisk root (su available via `adb shell su -c '...'`)
- Android NDK (r27d LTS recommended — one-time binary extraction, not
  active native dev; r28c does not exist despite some search results
  claiming otherwise)
- ADB (platform-tools)
- Homebrew's lldb recommended over Apple's bundled /usr/bin/lldb —
  the proven working recipe below was validated against Homebrew lldb
  (23.1.1); Apple's bundled lldb has not been ruled out but was not
  the version this recipe was proven against

## Extracting lldb-server
Pulled from the NDK, not built from source. The macOS NDK package is
a DMG containing an .app-bundle-shaped folder that is NOT a real
Finder app — double-clicking does nothing. Copy it out with `cp -R`
instead, then find the real binary nested under `Contents/NDK/`:

    Contents/NDK/toolchains/llvm/prebuilt/darwin-x86_64/lib/clang/18/lib/linux/aarch64/lldb-server

Confirm it's the right architecture:

    file lldb-server
    # ELF 64-bit LSB executable, ARM aarch64, statically linked

## Push to Device

    adb push lldb-server /data/local/tmp/lldb-server
    adb shell chmod 755 /data/local/tmp/lldb-server

## Start lldb-server — MUST run as root (su), MUST use platform mode

This is the single most important fix in this guide. Launching
lldb-server as plain shell (no su) or using `gdbserver --attach` mode
instead of `platform` mode both fail — the former loses the
connection on `process attach`, the latter segfaults lldb-server
itself outright (an Android NDK toolchain crash). Root + platform
mode is the only combination proven to work.

Use `0.0.0.0:<port>` (not `*:<port>`) as the listen address — a
bare `*` needs nested shell quoting that is easy to mangle on paste
(zsh will report `no matches found` from glob expansion if the
quoting breaks).

    adb shell "su -c '/data/local/tmp/lldb-server platform --listen 0.0.0.0:10500 --server &'"
    adb forward tcp:10500 tcp:10500

Port 10500 is this project's standard Android port — use it
consistently rather than improvising a different one per session.

## MACE Connection from M5

    lldb
    (lldb) platform select remote-android
    (lldb) settings set platform.plugin.remote-android.package-name <package.name>
    (lldb) settings set target.parallel-module-load false
    (lldb) process handle SIGSEGV -n false -p true -s false
    (lldb) process handle SIGBUS -n false -p true -s false
    (lldb) platform connect connect://localhost:10500

`settings set platform.plugin.remote-android.package-name` MUST be
set before `platform connect` — this is not optional, and there is
no equivalent `platform settings -c` syntax (that produces "unknown
or ambiguous option").

The SIGSEGV/SIGBUS passthrough is standard practice for every Android
session, not just a troubleshooting step: ART's JIT compiler generates
routine SIGSEGVs as part of normal null-check-elimination — not real
crashes.

## Launching and Attaching to the Target App

Find the real Activity name rather than guessing — Unity's newer
AndroidX GameActivity template, for example, uses
`UnityPlayerGameActivity`, not the older `UnityPlayerActivity`:

    adb shell cmd package resolve-activity --brief <package.name>
    adb shell am start -n <package.name>/<ActivityName>
    adb shell pidof <package.name>

Then in lldb:

    (lldb) process attach --pid <PID>
    (lldb) mace_on

A long stream of `No LZMA support found for reading .gnu_debugdata
section` warnings during attach is expected and cosmetic (this lldb
build lacks LZMA decompression for Android system libraries'
compressed mini-symbol-tables) — not an error, keep going.

## Setting Breakpoints in App Libraries (e.g. libil2cpp.so)

Confirm the module is actually loaded before setting a breakpoint —
`image list <substring>` filters directly, no piping to external
grep (lldb's own command parser owns the `|` character and will
reject a real shell pipe):

    (lldb) image list libil2cpp.so

To set a breakpoint at a known offset inside a loaded library without
knowing its ASLR-slid load address, use `--shlib`/`--address` — lldb
adds the real load bias for you:

    (lldb) breakpoint set --shlib <lib.so> --address <RVA>

Use the tool's **RVA** (virtual address per the ELF's own section
layout), not a raw file **byte offset** — they are not the same
number and only the RVA resolves correctly. (Il2CppDumper output, for
example, lists both `RVA:` and `Offset:` per method — use RVA here.)

## Cleaning Up Stray lldb-server Processes

A failed attach or a client disconnect does not always kill the
on-device lldb-server — leftover processes (including zombies) can
hold the port and cause `failed to listen: Address already in use`
on the next attempt. Check and clear before restarting:

    adb shell "su -c 'ps -A | grep lldb-server'"
    adb shell "su -c 'kill -9 <pid> <pid> ...'"

## mace_patch — Registers Only

`mace_patch` patches registers, not arbitrary memory addresses:

    (lldb) mace_patch w0 1

For patching a struct/instance field in memory (e.g. a managed
object's field via its `this` pointer + offset), use lldb's own
`memory write` instead:

    (lldb) memory write -s 4 <address> 0x00000000
