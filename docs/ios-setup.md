# MACE iOS Setup Guide

## Tested Configuration
- iPad 7th Gen (A10, iOS 18.7.2, palera1n semi-tethered)
- M5 MacBook Pro (LLDB + MACE)

## Prerequisites
- palera1n jailbreak
- Sileo package manager
- OpenSSH (Procursus repo)
- NewTerm 3
- debugserver-16 (Procursus repo)
- Filza File Manager (Havoc repo)

## First Time SSH Setup
palera1n does not start SSH automatically. On the iPad via NewTerm:

    su root
    mkdir -p /var/jb/etc/ssh
    ssh-keygen -t rsa -f /var/jb/etc/ssh/ssh_host_rsa_key -N ""
    ssh-keygen -t ecdsa -f /var/jb/etc/ssh/ssh_host_ecdsa_key -N ""
    ssh-keygen -t ed25519 -f /var/jb/etc/ssh/ssh_host_ed25519_key -N ""
    /var/jb/usr/sbin/sshd

## Every Session
palera1n is semi-tethered - re-run palera1n after reboot. Then:

    ssh root@<ipad-ip>
    /var/jb/usr/sbin/sshd
    export PATH="/var/jb/usr/lib/llvm-16/bin:$PATH"

Persist PATH:

    echo 'export PATH="/var/jb/usr/lib/llvm-16/bin:$PATH"' >> /var/jb/etc/profile

## debugserver

    which debugserver
    ps aux | grep <AppName>
    debugserver 0.0.0.0:1234 --attach=<PID>

## MACE Connection from M5

    lldb
    (lldb) platform select remote-ios
    (lldb) process connect connect://192.168.4.22:1234
    (lldb) mace_on

## Symbol Cache - eliminates parsing wait

### Step 1 - Try this first (recommended)
Point xcode-select at the full Xcode installation (see Critical Fix section below).
This alone eliminates the parsing delay for most configurations and should be
attempted before any manual cache handling.

### Step 2 - Optional fallback (if parsing is still slow after xcode-select fix)
One-time cache copy:

    mkdir -p ~/dyld_cache
    scp root@<ipad-ip>:/private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64* ~/dyld_cache/

Add to ~/.lldbinit:

    settings set target.exec-search-paths /Users/chidabangalore/dyld_cache

Note: After applying the xcode-select fix, manual cache handling is
typically unnecessary.

## IPA Re-signing for iOS 18
Required for older IPAs with outdated signatures.
Not required for App Store apps.

1. Export .p12 from Keychain Access - My Certificates tab
2. Find wildcard provisioning profile:

    for f in ~/Library/Developer/Xcode/UserData/Provisioning\ Profiles/*.mobileprovision; do
      echo "=== $(basename $f) ==="
      security cms -D -i "$f" 2>/dev/null | plutil -convert xml1 - -o - 2>/dev/null \
        | grep -A1 "<key>Name</key>" | head -3
    done

Use: iOS Team Provisioning Profile: *

3. Re-sign:

    zsign -k ~/Documents/Certificates.p12 -p <password> \
      -m ~/Library/Developer/Xcode/UserData/Provisioning\ Profiles/<uuid>.mobileprovision \
      -o App_signed.ipa -z 9 App_original.ipa

4. Install:

    ideviceinstaller install App_signed.ipa

Note: AppSync Unified repo (cydia.akemi.ai) offline as of July 2026.

## Session Management
- App crash/exit: new PID, re-attach debugserver
- Always quit LLDB fully before reconnecting
- Auto-Lock: Settings > Display & Brightness > Auto-Lock > Never

## MASTG UnCrackable Level 1 - Solved (July 19, 2026)
Technique: ObjC runtime view hierarchy dump

    (lldb) process interrupt
    (lldb) po [[[[UIApplication sharedApplication] windows] firstObject] recursiveDescription]

Found UILabel with hidden=YES containing: i am groot!
No Frida. No re-compilation. Pure debugger-native LLDB analysis.

## Critical Fix — xcode-select (eliminates 12-min parsing delay)

The single most important fix for LLDB iOS performance:

    sudo xcode-select -s /Applications/Xcode.app/Contents/Developer

Verify:
    xcrun --sdk iphoneos --show-sdk-path
    # Should show: /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/...

Without this, LLDB uses CommandLineTools which has no iOS SDK.
Result: 12+ minute symbol parsing from device RAM every session.
With this: instant connection, SDK found automatically.

## MASTG UnCrackable Level 2 — Anti-Debug Analysis (July 26, 2026)

L2 has layered anti-debugging defenses:
1. ptrace(PT_DENY_ATTACH) — called on launch
2. Background detection thread — repeatedly calls ptrace + exit(0)
3. Multiple threads spawned in a loop

Bypass approach:
- Use debugserver --waitfor (intercept before ptrace fires)
- Set breakpoints on __ptrace and exit before first continue
- Patch ptrace: reg write x0 0 (changes PT_DENY_ATTACH=31 to 0)
- Patch exit: thread return (prevents exit from executing)
- L2 spawns detection loop — requires automated patching or bypass tweak

Status: App UI reached after manual patching. Detection loop 
requires Liberty Lite or automated br command solution.

Note: Anti-debug bypass is currently treated as external target-preparation
infrastructure. MACE analysis begins once a stable LLDB session is established.
Detection and annotation of anti-debug patterns may be added as a future
MACE capability.
