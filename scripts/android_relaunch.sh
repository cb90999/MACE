#!/bin/bash
# scripts/android_relaunch.sh
#
# Force-stops, relaunches, and prints the pid of the app under test.
# Run after scripts/android_device_prep.sh and before
# scripts/android_connect.sh.
#
# Usage: scripts/android_relaunch.sh <package[/activity]>
# e.g. scripts/android_relaunch.sh com.chidabangalore.enigma/.MainActivity

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <package[/activity]>" >&2
    exit 1
fi

TARGET="$1"
PACKAGE="${TARGET%%/*}"

echo "[relaunch] Force-stopping ${PACKAGE}..."
adb shell am force-stop "${PACKAGE}"

echo "[relaunch] Starting ${TARGET}..."
adb shell am start -n "${TARGET}"

echo "[relaunch] Waiting for process..."
PID=""
for i in $(seq 1 20); do
    PID="$(adb shell pidof "${PACKAGE}" || true)"
    if [[ -n "${PID}" ]]; then
        break
    fi
    sleep 0.25
done

if [[ -z "${PID}" ]]; then
    echo "[relaunch] ERROR: ${PACKAGE} did not start (no pid found)." >&2
    exit 1
fi

echo "${PACKAGE}" > .mace_android_target
echo "[relaunch] ${PACKAGE} running, pid ${PID}"
