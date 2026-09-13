# Android LLDB Troubleshooting on Android 16

## Purpose

This document captures a complete troubleshooting session for native Android debugging with LLDB on a rooted Pixel 10a running Android 16 (API 36).

The goal was to determine why named native breakpoints failed to resolve in a debuggable Android application even though raw-address breakpoints worked.

The final result showed that the problem was **not an inherent Android 16 or LLDB limitation**. The failure was specific to the earlier raw `lldb-server gdbserver --attach` workflow, which provided process/thread/memory access but did not populate LLDB's executable/module model.

Using:

- `lldb-server platform`
- LLDB's `remote-android` platform plugin
- the Android package name
- PID-based attach

correctly populated the module list, discovered the application native library, resolved symbols and DWARF source information, and allowed named breakpoints to bind and hit successfully.

---

## Test Environment

### Host

- macOS on Apple Silicon
- Homebrew LLDB 23.1.1
- Apple LLDB also present at `/usr/bin/lldb`
- Android SDK under:

```text
~/Library/Android/sdk
```

### Device

- Google Pixel 10a
- Android 16
- API level 36
- ABI: `arm64-v8a`
- Rooted device

### Application

Package:

```text
com.mace.eeavalidation
```

Launcher activity:

```text
com.mace.eeavalidation/.MainActivity
```

Native library:

```text
libeea.so
```

JNI entry point:

```text
Java_com_mace_eeavalidation_MainActivity_checkInput
```

Native validation function:

```text
validate
```

---

# 1. Establish Device and Host Baseline

Confirm that the device is connected:

```bash
adb devices -l
```

Check device characteristics:

```bash
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell getprop ro.product.cpu.abi
```

Observed:

```text
Pixel 10a
16
36
arm64-v8a
```

Check which LLDB is being used:

```bash
which lldb
lldb --version
```

Initially:

```text
/usr/bin/lldb
lldb-2100.0.17.203
Apple Swift version 6.3.3
```

This was Apple's LLDB, not an upstream/Homebrew LLVM LLDB.

---

# 2. Locate Android NDK Installations

List installed NDKs:

```bash
ls -la ~/Library/Android/sdk/ndk
```

Observed installations:

```text
27.3.13750724
28.2.13676358
```

Locate available `lldb-server` binaries:

```bash
find ~/Library/Android/sdk/ndk -type f -name lldb-server 2>/dev/null
```

For the Pixel 10a, use the AArch64 build:

```text
~/Library/Android/sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/darwin-x86_64/lib/clang/19/lib/linux/aarch64/lldb-server
```

---

# 3. Install a Host LLDB

Install Homebrew LLDB:

```bash
brew install lldb
```

Verify:

```bash
brew --prefix lldb
```

Observed:

```text
/opt/homebrew/opt/lldb
```

Check version:

```bash
"$(brew --prefix lldb)/bin/lldb" --version
```

Observed:

```text
lldb version 23.1.1
```

Verify architecture:

```bash
file "$(brew --prefix lldb)/bin/lldb"
```

Observed:

```text
Mach-O 64-bit executable arm64
```

The `LDFLAGS` and `CPPFLAGS` suggestions printed by Homebrew were not needed because LLDB was being executed directly rather than linked into another program.

---

# 4. Push `lldb-server` to the Pixel

Push the AArch64 server from NDK 28.2:

```bash
adb push \
~/Library/Android/sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/darwin-x86_64/lib/clang/19/lib/linux/aarch64/lldb-server \
/data/local/tmp/lldb-server-ndk28
```

Make it executable:

```bash
adb shell chmod 755 /data/local/tmp/lldb-server-ndk28
```

Verify the binary:

```bash
adb shell file /data/local/tmp/lldb-server-ndk28
```

Observed:

```text
ELF executable, 64-bit LSB arm64, static, for Android 30
```

Check the server version:

```bash
adb shell /data/local/tmp/lldb-server-ndk28 version
```

Observed:

```text
lldb version 19.0.1
clang revision 97a699bf4812a18fb657c2779f5296a4ab2694d2
llvm revision 97a699bf4812a18fb657c2779f5296a4ab2694d2
```

This created a deliberate version mismatch:

```text
Host LLDB:          23.1.1
Device lldb-server: 19.0.1
```

Despite that mismatch, the workflow below worked correctly.

---

# 5. Confirm the Application Is Debuggable

Locate the package:

```bash
adb shell pm list packages | grep -i eea
```

Observed:

```text
package:com.mace.eeavalidation
```

Resolve package path:

```bash
adb shell pm path com.mace.eeavalidation
```

Test `run-as`:

```bash
adb shell run-as com.mace.eeavalidation id
```

A successful `run-as` confirmed that the installed application was debuggable.

---

# 6. Pull the APK into `/tmp`

Copy the APK into a disposable host-side workspace:

```bash
adb pull \
/data/app/.../com.mace.eeavalidation-.../base.apk \
/tmp/eea-base.apk
```

List native ARM64 libraries:

```bash
unzip -l /tmp/eea-base.apk | grep 'lib/arm64-v8a/.*\.so'
```

Observed:

```text
lib/arm64-v8a/libeea.so
```

The APK also contained:

```text
lib/armeabi-v7a/libeea.so
lib/x86_64/libeea.so
```

For the Pixel 10a, only the ARM64 library was relevant.

---

# 7. Extract the ARM64 Native Library into `/tmp`

Create a temporary extraction directory:

```bash
mkdir -p /tmp/eea-arm64
cd /tmp/eea-arm64
```

Extract the library:

```bash
unzip -o /tmp/eea-base.apk lib/arm64-v8a/libeea.so
```

Result:

```text
/tmp/eea-arm64/lib/arm64-v8a/libeea.so
```

---

# 8. Establish ELF and Symbol Ground Truth

Set the NDK LLVM tools directory:

```bash
NDK_BIN=~/Library/Android/sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/darwin-x86_64/bin
```

Inspect the ELF:

```bash
file /tmp/eea-arm64/lib/arm64-v8a/libeea.so
```

Observed:

```text
ELF 64-bit LSB shared object, ARM aarch64
with debug_info
not stripped
```

List symbols:

```bash
$NDK_BIN/llvm-nm -C /tmp/eea-arm64/lib/arm64-v8a/libeea.so
```

Important symbols included:

```text
Java_com_mace_eeavalidation_MainActivity_checkInput
validate
modular_hash
extended_gcd
normalize_mod
pack_little_endian
```

The key exported functions were:

```text
0000000000000968 T Java_com_mace_eeavalidation_MainActivity_checkInput
00000000000007e8 T validate
```

Check debug sections:

```bash
$NDK_BIN/llvm-readelf -S /tmp/eea-arm64/lib/arm64-v8a/libeea.so \
  | grep -E 'debug_|symtab|dynsym'
```

Observed sections included:

```text
.dynsym
.debug_abbrev
.debug_info
.debug_ranges
.debug_str
.debug_line
.symtab
```

This proved, before LLDB was involved, that:

- the symbol existed,
- the ELF was not stripped,
- DWARF debug information existed,
- source-level debugging should be possible.

---

# 9. Identify the Launch Activity

Resolve the launchable activity:

```bash
adb shell cmd package resolve-activity --brief com.mace.eeavalidation
```

Observed:

```text
com.mace.eeavalidation/.MainActivity
```

Stop the app:

```bash
adb shell am force-stop com.mace.eeavalidation
```

Confirm no process exists:

```bash
adb shell pidof com.mace.eeavalidation
```

Expected:

```text
<no output>
```

---

# 10. Avoid Loading MACE During the Baseline Test

Launching Homebrew LLDB normally triggered MACE imports from the LLDB initialization file and failed with:

```text
ModuleNotFoundError: No module named 'mace'
```

For a clean baseline, launch LLDB without init files:

```bash
/opt/homebrew/opt/lldb/bin/lldb --no-lldbinit
```

This keeps MACE completely out of the experiment.

---

# 11. Verify the `remote-android` Plugin

Inside clean LLDB:

```lldb
platform list
```

Confirmed:

```text
remote-android: Remote Android user platform plug-in.
```

Select it:

```lldb
platform select remote-android
```

---

# 12. Start `lldb-server` in Platform Mode

The successful architecture used **platform mode**, not the earlier raw `gdbserver --attach` path.

Clean stale forwards:

```bash
adb forward --remove-all
```

Create forwarding:

```bash
adb forward tcp:5040 tcp:5040
```

Start the platform server on the Pixel:

```bash
adb shell su -c '/data/local/tmp/lldb-server-ndk28 platform --listen 127.0.0.1:5040 --server'
```

Leave this terminal running.

## Stale Server Troubleshooting

At one point an old root-owned `lldb-server` remained running.

A normal shell could see but not terminate it:

```text
pkill: Operation not permitted
```

Inspect:

```bash
adb shell ps -A | grep lldb
```

Because the process was root-owned, terminate it via `su`:

```bash
adb shell su -c 'kill -9 <PID1> <PID2>'
```

Verify:

```bash
adb shell ps -A | grep lldb
```

Expected:

```text
<no output>
```

---

# 13. Connect LLDB Through `remote-android`

Launch clean LLDB:

```bash
/opt/homebrew/opt/lldb/bin/lldb --no-lldbinit
```

Inside LLDB:

```lldb
platform select remote-android
```

Set the package name:

```lldb
settings set platform.plugin.remote-android.package-name com.mace.eeavalidation
```

Connect:

```lldb
platform connect connect://localhost:5040
```

Successful result:

```text
Platform: remote-android
Triple: aarch64-unknown-linux-android
OS Version: 36
Connected: yes
WorkingDir: /
```

## Important Connection Detail

The successful connection used:

```text
connect://localhost:5040
```

An earlier attempt using:

```text
connect://127.0.0.1:5040
```

returned:

```text
error: Invalid URL
```

In this environment, `localhost` worked where `127.0.0.1` did not.

---

# 14. APKs Cannot Be Passed Directly to `target create`

This attempt failed:

```lldb
target create /tmp/eea-base.apk
```

with:

```text
'/tmp/eea-base.apk' is not a valid executable
```

That is expected because an APK is a ZIP/container, not an ELF executable.

The successful workflow used normal Android application startup followed by LLDB attach.

---

# 15. Start the Application Normally

From another terminal:

```bash
adb shell am start -n com.mace.eeavalidation/.MainActivity
```

Get its PID:

```bash
adb shell pidof com.mace.eeavalidation
```

Example:

```text
1678
```

---

# 16. Attach by PID Through `remote-android`

From the already-connected LLDB session:

```lldb
process attach --pid 1678
```

This was the critical difference from the failing raw gdbserver attach workflow.

LLDB automatically:

- stopped the process,
- discovered `app_process64`,
- set architecture to `aarch64-unknown-linux-android`,
- populated the loaded module list.

Observed:

```text
Executable binary set to ".../app_process64".
Architecture set to: aarch64-unknown-linux-android.
```

---

# 17. Verify Module Discovery

Run:

```lldb
image list
```

Unlike the earlier failing workflow, this produced a fully populated module list.

Modules included:

```text
app_process64
libc.so
linker64
libart.so
libandroid_runtime.so
libbinder.so
libgui.so
libhwui.so
...
libeea.so
```

The application native library appeared as:

```text
libeea.so
```

with the same Build ID observed locally.

This proved that the `remote-android` platform path correctly reconstructed LLDB's target/module model.

---

# 18. Resolve the Application Symbol

Run:

```lldb
image lookup -n validate
```

Many Android libraries contained symbols named `validate`, but importantly LLDB also found:

```text
libeea.so`validate at eea.c:44
```

The application function was resolved to:

```text
libeea.so[0x00000000000007e8]
```

This proved:

- the module was loaded,
- LLDB indexed the symbol,
- DWARF was recognized,
- source-file information was available.

---

# 19. Why a Bare `b validate` Is Too Broad

Running:

```lldb
b validate
```

created:

```text
Breakpoint 1: 53 locations.
```

Android contains many unrelated functions named `validate`.

This demonstrated that named-symbol lookup was working, but the breakpoint was far too broad.

The correct approach is to qualify the breakpoint by module.

---

# 20. Set a Module-Qualified Native Breakpoint

Use:

```lldb
breakpoint set -n validate -s libeea.so
```

Observed:

```text
Breakpoint 2:
where = libeea.so`validate + 16 at eea.c:45:25
address = 0x...
```

`breakpoint list` showed:

```text
name = 'validate'
module = libeea.so
locations = 1
resolved = 1
```

This was definitive proof that the application-specific named breakpoint resolved correctly.

---

# 21. Set the JNI Entry-Point Breakpoint

Use one LLDB command on one line:

```lldb
breakpoint set -n Java_com_mace_eeavalidation_MainActivity_checkInput -s libeea.so
```

Do not use shell-style trailing backslashes inside LLDB.

Observed:

```text
Breakpoint 3:
where = libeea.so`Java_com_mace_eeavalidation_MainActivity_checkInput + 24
at eea.c:59:9
```

`breakpoint list` showed:

```text
locations = 1
resolved = 1
```

---

# 22. ART SIGSEGV Behavior

After:

```lldb
continue
```

LLDB initially stopped on:

```text
signal SIGSEGV
```

inside JIT-generated ART code:

```text
android.os.MessageStack.heapSweep
```

This was not evidence that `libeea.so` had crashed.

Inspect the signal policy:

```lldb
process handle SIGSEGV
```

Initial result:

```text
PASS   true
STOP   true
NOTIFY true
```

This meant LLDB passed the signal to the process but also stopped and notified on every SIGSEGV.

Change the policy:

```lldb
process handle -s false -n false -p true SIGSEGV
```

Verify:

```lldb
process handle SIGSEGV
```

Desired result:

```text
PASS   true
STOP   false
NOTIFY false
```

This allowed ART to handle the signal normally while LLDB continued toward the real native breakpoints.

---

# 23. Hit the JNI Breakpoint

Resume:

```lldb
continue
```

Trigger the validation action in the EEA app.

LLDB stopped at:

```text
libeea.so`Java_com_mace_eeavalidation_MainActivity_checkInput
```

at:

```text
eea.c:59
```

Backtrace:

```lldb
bt
```

Observed:

```text
frame #0 libeea.so`Java_com_mace_eeavalidation_MainActivity_checkInput
frame #1 libart.so`art_quick_generic_jni_trampoline
frame #2 libart.so`art_quick_invoke_stub
```

Inspect locals:

```lldb
frame variable
```

Example output included:

```text
(JNIEnv *) env
(jobject) thiz
(jstring) input
(const char *) native_input
(int) result
```

This confirmed the managed-to-native JNI transition.

---

# 24. Hit the `validate()` Breakpoint

Continue again:

```lldb
continue
```

LLDB stopped at:

```text
libeea.so`validate
```

with source mapping:

```text
eea.c:45
```

The argument was decoded correctly:

```text
input="jjjjj"
```

The source line was:

```c
size_t len = strlen(input);
```

This completed the full runtime validation.

---

# 25. Final Proven Chain

The successful workflow proved:

```text
Android app starts normally
        ↓
LLDB remote-android connects
        ↓
PID attach succeeds
        ↓
app_process64 discovered
        ↓
ART/system/native modules populated
        ↓
libeea.so discovered
        ↓
ELF/DWARF symbols loaded
        ↓
module-qualified named breakpoints resolve
        ↓
JNI breakpoint hits
        ↓
validate() breakpoint hits
        ↓
source and arguments are visible
```

---

# 26. Root Cause of the Earlier Named-Symbol Failure

The earlier failing workflow used:

```text
lldb-server gdbserver --attach
```

That path allowed:

- attaching to a process,
- enumerating threads,
- stopping execution,
- reading registers,
- reading memory,
- using raw-address breakpoints.

However, LLDB reported:

```text
Target 0: (No executable module.)
```

and `image list` did not provide a useful executable/module model.

As a consequence, named breakpoints could remain pending even when the symbol genuinely existed.

The corrected root cause is:

> The named-symbol failure was not caused by Android 16 itself and was not caused by the native ELF lacking symbols. It was caused by using a raw gdbserver attach path that did not populate LLDB's Android-aware executable/module model.

The successful path was:

```text
lldb-server platform
        +
LLDB remote-android plugin
        +
package-name setting
        +
PID attach
```

---

# 27. Key Troubleshooting Lessons

## Use clean LLDB when validating LLDB itself

```bash
/opt/homebrew/opt/lldb/bin/lldb --no-lldbinit
```

This prevents MACE or other LLDB startup scripts from changing the experiment.

## Establish ELF ground truth before blaming LLDB

Use:

```bash
file
llvm-nm
llvm-readelf
```

Confirm:

- correct ABI,
- symbol presence,
- `.symtab`,
- `.dynsym`,
- DWARF sections.

## Use `/tmp` for disposable APK and ELF inspection

Example:

```text
/tmp/eea-base.apk
/tmp/eea-arm64/lib/arm64-v8a/libeea.so
```

This keeps temporary debugging material separate from the source repository.

## Prefer module-qualified breakpoints

Avoid:

```lldb
b validate
```

Prefer:

```lldb
breakpoint set -n validate -s libeea.so
```

## For ART apps, inspect signal policy

If LLDB repeatedly stops in JIT/ART code on SIGSEGV:

```lldb
process handle SIGSEGV
```

If appropriate for the controlled test:

```lldb
process handle -s false -n false -p true SIGSEGV
```

## Do not assume APKs can be used with `target create`

This fails:

```lldb
target create app.apk
```

Instead:

- launch the app with Android tools,
- attach to the process,
- let `remote-android` build the module model.

## Root-owned stale `lldb-server` processes may need `su`

```bash
adb shell ps -A | grep lldb
adb shell su -c 'kill -9 <PID>'
```

## Shell continuation syntax does not carry into LLDB

Use one line:

```lldb
breakpoint set -n symbol -s module.so
```

---

# 28. Recommended Baseline Workflow

For future Android native LLDB troubleshooting:

```bash
# Stop app
adb shell am force-stop <package>

# Clean stale debugger state
adb forward --remove-all

# Inspect/kill stale server if needed
adb shell ps -A | grep lldb
adb shell su -c 'kill -9 <PID>'

# Forward platform port
adb forward tcp:5040 tcp:5040

# Start platform-mode server
adb shell su -c '/data/local/tmp/lldb-server platform --listen 127.0.0.1:5040 --server'
```

In another terminal:

```bash
/opt/homebrew/opt/lldb/bin/lldb --no-lldbinit
```

Inside LLDB:

```lldb
platform select remote-android
settings set platform.plugin.remote-android.package-name <package>
platform connect connect://localhost:5040
```

Launch the app:

```bash
adb shell am start -n <package>/<activity>
adb shell pidof <package>
```

Attach:

```lldb
process attach --pid <PID>
```

Validate module discovery:

```lldb
image list
```

Resolve a known symbol:

```lldb
image lookup -n <symbol>
```

Set a module-qualified breakpoint:

```lldb
breakpoint set -n <symbol> -s <module.so>
```

If ART-generated SIGSEGV stops interfere with the test:

```lldb
process handle -s false -n false -p true SIGSEGV
```

Resume:

```lldb
continue
```

---

# 29. Architectural Takeaway for MACE

This session suggests that Android support in MACE should distinguish between debugger transport modes.

A raw gdbserver attach may provide:

```text
threads
registers
memory
raw-address breakpoints
```

while lacking a complete LLDB module model.

A `remote-android` platform session can additionally provide:

```text
Android-aware module discovery
app_process64 association
module cache population
ELF symbol resolution
DWARF/source mapping
module-qualified named breakpoints
```

MACE should therefore avoid assuming that a successful process attach implies symbolic debugging is available.

A future capability check could explicitly test:

```text
process attached?
module list populated?
target executable known?
requested module present?
symbol resolved?
breakpoint resolved?
```

This would allow MACE to distinguish an address-only session from a full symbolic Android debugging session.

---

# 30. Result

The final test successfully hit both:

```text
Java_com_mace_eeavalidation_MainActivity_checkInput
```

and:

```text
validate
```

inside `libeea.so`.

LLDB displayed:

- source file and line,
- JNI arguments,
- native function arguments,
- ART-to-JNI transition frames,
- correct application module load address.

The Android named-symbol debugging path was therefore confirmed functional on:

```text
Pixel 10a
Android 16 / API 36
arm64-v8a
Homebrew LLDB 23.1.1
lldb-server 19.0.1
remote-android platform mode
```

The main troubleshooting conclusion is:

> On this Android 16 setup, the raw `lldb-server gdbserver --attach` path was insufficient for reliable named-symbol debugging because LLDB's executable/module model was not populated. `lldb-server platform` with `remote-android` and PID attach restored complete module and symbol awareness.
