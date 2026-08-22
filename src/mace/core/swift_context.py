"""
MACE — Mobile AArch64 Context Extension
core/swift_context.py

Swift binary context via swift-section CLI.
Parses type names and field offsets for Swift annotation layer.
"""

import subprocess
import re
from pathlib import Path


class SwiftContext:
    """
    Parses swift-section output to provide Swift type information
    for MACE's annotation layer.
    """

    def __init__(self, binary_path: str, exe_ctx=None):
        self.binary_path = binary_path
        self.load_error: str = ""       # last failure reason, for caller diagnostics
        self._type_map: dict[str, str] = {}      # mangled -> human name
        self._field_map: dict[str, dict] = {}    # type -> {offset: field_name}
        self._func_map: dict[str, str] = {}      # partial name -> full name
        self._loaded = False
        self._load(exe_ctx)

    def _resolve_local_path(self, exe_ctx) -> str:
        """
        If binary_path doesn't exist on the local filesystem (e.g. a
        device-only path like /private/var/containers/... on a remote
        iOS target), try to resolve it via LLDB's own module cache.
        When attached to a remote target, LLDB already holds a local
        file spec for loaded modules -- reuse that instead of asking
        swift-section (a separate local process) to read a path that
        only exists on the device.
        """
        if Path(self.binary_path).exists():
            return self.binary_path

        if exe_ctx is None:
            return self.binary_path  # nothing else we can try

        target = exe_ctx.GetTarget()
        if not target or not target.IsValid():
            return self.binary_path

        basename = Path(self.binary_path).name
        for module in target.module_iter():
            file_spec = module.GetFileSpec()
            if file_spec and file_spec.GetFilename() == basename:
                local_spec = module.GetFileSpec()
                local_path = str(Path(local_spec.GetDirectory() or "") / local_spec.GetFilename())
                if Path(local_path).exists():
                    return local_path
        return self.binary_path  # fall through; _load will report the failure

    def _load(self, exe_ctx=None) -> None:
        """Run swift-section and parse output."""
        resolved_path = self._resolve_local_path(exe_ctx)

        if not Path(resolved_path).exists():
            self.load_error = (
                f"'{resolved_path}' does not exist on the local filesystem. "
                f"swift-section runs on the host machine and cannot read "
                f"device-only paths directly. Either scp the binary/dylib "
                f"to the M5 first and pass that local path, or attach to "
                f"the target so MACE can resolve it from LLDB's module cache."
            )
            return

        try:
            result = subprocess.run(
                ["swift-section", "dump",
                 "--architecture", "arm64",
                 "--emit-field-offsets",
                 resolved_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                self._parse(result.stdout)
                self._loaded = True
            else:
                self.load_error = (
                    f"swift-section exited {result.returncode}: "
                    f"{result.stderr.strip() or '(no stderr output)'}"
                )
        except FileNotFoundError:
            self.load_error = "swift-section is not installed or not on PATH."
        except subprocess.TimeoutExpired:
            self.load_error = "swift-section timed out after 30s."

    def _parse(self, output: str) -> None:
        """Parse swift-section dump output."""
        current_type = None
        for line in output.splitlines():
            line = line.strip()

            # Type declaration
            m = re.match(r'^(?:struct|class|enum|protocol)\s+(\S+)\s*\{', line)
            if m:
                current_type = m.group(1)
                self._field_map[current_type] = {}
                continue

            # Field offset
            m = re.match(r'^//\s*Field offset:\s*(0x[0-9a-fA-F]+)', line)
            if m and current_type:
                self._pending_offset = int(m.group(1), 16)
                continue

            # Field declaration after offset comment
            if hasattr(self, '_pending_offset') and current_type:
                m = re.match(r'^(?:var|let)\s+(\w+):\s*(.+)', line)
                if m:
                    field_name = m.group(1)
                    field_type = m.group(2)
                    self._field_map[current_type][self._pending_offset] = {
                        'name': field_name,
                        'type': field_type
                    }
                    del self._pending_offset
                    continue

            # Function
            m = re.match(r'^(?:static\s+)?(\S+\.\S+)\(.*\)\s*->', line)
            if m and current_type:
                fname = m.group(1)
                short = fname.split('.')[-1]
                self._func_map[short] = fname

    def type_for_address(self, binary_name: str) -> str:
        """
        Best-effort type name from binary name.
        Returns first non-system type found when binary_name matches module.
        """
        if not self._loaded or not binary_name:
            return ""
        module = binary_name.split('.')[0].replace(' ', '')
        for type_name in self._field_map:
            if module and type_name.startswith(module + '.'):
                return type_name
        return ""

    def type_for_function(self, function_name: str) -> str:
        """
        Resolve Swift type from LLDB function name.
        e.g. "ContentView.runChecks() at ContentView.swift:58"
        returns "MACESecurityTest.ContentView"
        """
        if not self._loaded or not function_name:
            return ""
        # Strip file/line info
        fname = function_name.split(' at ')[0].strip()
        # Try matching against known types
        for type_name in self._field_map:
            short = type_name.split('.')[-1]
            if short and (fname.startswith(short + '.') or
                         f'.{short}.' in fname or
                         fname.startswith(short + '(')):
                return type_name
        return ""

    def selector_for_function(self, function_name: str) -> str:
        """
        Extract method/function name from LLDB function symbol.
        e.g. "ContentView.runChecks() at ContentView.swift:58"
        returns "runChecks()"
        """
        if not function_name:
            return ""
        fname = function_name.split(' at ')[0].strip()
        # Extract last component after dot
        parts = fname.split('.')
        if len(parts) >= 2:
            return parts[-1].split('(')[0]
        return ""

    def field_at_offset(self, type_name: str, offset: int) -> str:
        """Return field name at given offset within type."""
        if not self._loaded:
            return ""
        fields = self._field_map.get(type_name, {})
        entry = fields.get(offset)
        if entry:
            return f"{entry['name']}: {entry['type']}"
        return ""

    def all_types(self) -> list[str]:
        """Return all known Swift type names."""
        return list(self._field_map.keys())

    def is_loaded(self) -> bool:
        return self._loaded
