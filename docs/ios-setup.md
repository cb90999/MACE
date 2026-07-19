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

## Symbol Cache - eliminates 2-5 min parsing wait
One-time setup:

    mkdir -p ~/dyld_cache
    scp root@192.168.4.22:/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64 ~/dyld_cache/

Add to ~/.lldbinit:

    settings set target.exec-search-paths /Users/chidabangalore/dyld_cache

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
