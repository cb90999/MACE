#!/usr/bin/env bash
# MACE — Android device-prep script
#
# Layer 1 of the per-platform connect automation (see BACKLOG.md,
# "Automate the full connect sequence per platform, not as one unified
# script", 2026-09-27). No lldb dependency at all — this only gets
# lldb-server running and reachable on the device; the lldb-side
# connect sequence (platform select, settings, process attach) is
# Layer 2, a separate mace_connect_android lldb command.
#
# Encodes every manual-sequence mistake from real sessions:
#   - stale lldb-server process left over from a prior session
#     ("Address already in use" on next attempt)
#   - adb forward silently not registering right after an adb daemon
#     restart (observed live 2026-10-02 — adb crashed mid-session,
#     came back, and the old forward just wasn't there anymore)
#   - zero feedback on whether lldb-server actually started at all
#
# Usage:
#   scripts/android_device_prep.sh [PORT] [LOCAL_LLDB_SERVER_PATH]
#
#   PORT                   default 10500 (project standard — see
#                          docs/android-setup.md)
#   LOCAL_LLDB_SERVER_PATH only needed the first time, or after a
#                          device wipe — path to the lldb-server
#                          binary extracted from the Android NDK
#                          (see docs/android-setup.md "Extracting
#                          lldb-server"). If omitted, this script
#                          expects one already pushed to the device.
#
# Safe to re-run — idempotent. Does not touch lldb itself.

set -uo pipefail

PORT="${1:-10500}"
LOCAL_LLDB_SERVER="${2:-}"
DEVICE_LLDB_SERVER="/data/local/tmp/lldb-server"

echo "[prep] Checking adb connectivity..."
if ! adb start-server >/dev/null 2>&1; then
    echo "[prep] ERROR: adb server failed to start. Check USB connection / platform-tools install." >&2
    exit 1
fi

DEVICE_COUNT=$(adb devices | grep -w "device" | wc -l | tr -d ' ')
if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo "[prep] ERROR: no device attached (adb devices shows none in 'device' state)." >&2
    adb devices
    exit 1
elif [ "$DEVICE_COUNT" -gt 1 ]; then
    echo "[prep] ERROR: multiple devices attached — set \$ANDROID_SERIAL or unplug extras." >&2
    adb devices
    exit 1
fi

DEVICE_SERIAL=$(adb devices | grep -w "device" | awk '{print $1}')
echo "[prep] One device confirmed: $DEVICE_SERIAL"

# Push a fresh lldb-server only if a local path was given — otherwise
# trust whatever's already on the device (the common case).
if [ -n "$LOCAL_LLDB_SERVER" ]; then
    if [ ! -f "$LOCAL_LLDB_SERVER" ]; then
        echo "[prep] ERROR: $LOCAL_LLDB_SERVER not found." >&2
        exit 1
    fi
    echo "[prep] Pushing lldb-server from $LOCAL_LLDB_SERVER..."
    adb push "$LOCAL_LLDB_SERVER" "$DEVICE_LLDB_SERVER"
    adb shell chmod 755 "$DEVICE_LLDB_SERVER"
else
    if ! adb shell "test -f $DEVICE_LLDB_SERVER" >/dev/null 2>&1; then
        echo "[prep] ERROR: no lldb-server found at $DEVICE_LLDB_SERVER on device," >&2
        echo "[prep]        and no local path given to push one." >&2
        echo "[prep]        Re-run with: $0 $PORT /path/to/local/lldb-server" >&2
        exit 1
    fi
    echo "[prep] Using existing on-device lldb-server at $DEVICE_LLDB_SERVER"
fi

echo "[prep] Checking for stale lldb-server processes..."
STALE_PIDS=$(adb shell "su -c 'ps -A | grep lldb-server'" | awk '{print $2}' | tr '\n' ' ')
STALE_PIDS="${STALE_PIDS% }"
if [ -n "$STALE_PIDS" ]; then
    echo "[prep] Found stale process(es): $STALE_PIDS — killing..."
    # shellcheck disable=SC2086
    adb shell "su -c 'kill -9 $STALE_PIDS'"
    sleep 1
else
    echo "[prep] No stale lldb-server processes found."
fi

echo "[prep] Starting lldb-server in platform mode (port $PORT)..."
adb shell "su -c '$DEVICE_LLDB_SERVER platform --listen 0.0.0.0:$PORT --server >/dev/null 2>&1 &'"
sleep 1

RUNNING_PID=$(adb shell "su -c 'pidof lldb-server'" | tr -d '\r\n ')
if [ -z "$RUNNING_PID" ]; then
    echo "[prep] ERROR: lldb-server did not start." >&2
    echo "[prep]        Common causes: wrong binary architecture (file lldb-server" >&2
    echo "[prep]        should show 'ELF 64-bit LSB executable, ARM aarch64'), or" >&2
    echo "[prep]        launching without platform mode (platform mode is required —" >&2
    echo "[prep]        see docs/android-setup.md)." >&2
    exit 1
fi
echo "[prep] lldb-server running, pid $RUNNING_PID"

echo "[prep] Forwarding tcp:$PORT..."
adb forward "tcp:$PORT" "tcp:$PORT" >/dev/null

# Verify the forward actually registered rather than trusting the
# command's exit status alone — observed live 2026-10-02 that a
# forward issued right after an adb daemon restart can silently not
# register on the first try.
if ! adb forward --list | grep -q "tcp:$PORT tcp:$PORT"; then
    echo "[prep] Forward did not register on first try, retrying once..."
    sleep 1
    adb forward "tcp:$PORT" "tcp:$PORT" >/dev/null
    if ! adb forward --list | grep -q "tcp:$PORT tcp:$PORT"; then
        echo "[prep] ERROR: port forward still not registered after retry." >&2
        echo "[prep]        Run 'adb forward --list' manually to check, or 'adb kill-server'" >&2
        echo "[prep]        followed by 'adb start-server' if the daemon seems stuck." >&2
        exit 1
    fi
fi

echo "[prep] Done. lldb-server listening on 0.0.0.0:$PORT, forwarded to localhost:$PORT."
echo "[prep] Next: in lldb, run 'platform select remote-android' and the rest of"
echo "[prep]       docs/android-setup.md's MACE Connection steps (or mace_connect_android"
echo "[prep]       once that lands)."
