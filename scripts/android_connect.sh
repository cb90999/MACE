#!/bin/bash
# scripts/android_connect.sh
#
# Starts lldb and runs the full Android connect sequence (platform
# select, package name, parallel-module-load off, signal handling,
# platform connect, attach). Drops you into an interactive lldb
# session already attached -- breakpoints and mace_on are still
# yours to set per debugging session.
#
# Usage: scripts/android_connect.sh [package] [pid]
# Package defaults to whatever scripts/android_relaunch.sh last used
# (read from .mace_android_target). Pid defaults to auto-detect via
# pidof for that package.

set -euo pipefail

PACKAGE="${1:-}"
PID="${2:-}"

if [[ -z "${PACKAGE}" ]]; then
    if [[ -f .mace_android_target ]]; then
        PACKAGE="$(cat .mace_android_target)"
    else
        echo "[connect] ERROR: no package given and no .mace_android_target found." >&2
        echo "          Run scripts/android_relaunch.sh <package> first, or pass one explicitly." >&2
        exit 1
    fi
fi

if [[ -z "${PID}" ]]; then
    PID="$(adb shell pidof "${PACKAGE}")"
    if [[ -z "${PID}" ]]; then
        echo "[connect] ERROR: ${PACKAGE} not running. Run scripts/android_relaunch.sh first." >&2
        exit 1
    fi
fi

echo "[connect] Attaching to ${PACKAGE} (pid ${PID})..."

lldb -o "platform select remote-android" \
     -o "settings set platform.plugin.remote-android.package-name ${PACKAGE}" \
     -o "settings set target.parallel-module-load false" \
     -o "process handle SIGSEGV -n false -p true -s false" \
     -o "process handle SIGBUS -n false -p true -s false" \
     -o "platform connect connect://localhost:10500" \
     -o "process attach --pid ${PID}"
