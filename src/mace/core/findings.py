"""
MACE — Mobile AArch64 Context Extension
core/findings.py

Loads a findings-JSON file (a tool-agnostic handoff format a static-RE
tool -- or a human -- could produce) and tracks which breakpoints it
set, so the stop-hook/display layer can annotate a hit with that
finding's kind/note/suggested_action instead of the analyst needing to
already know what they're looking at.

Schema (MVP, see BACKLOG.md's 2026-10-31/2026-11-02 entries for design
history):
{
  "target": "eeacollatz",
  "platform": "ios",
  "binary": "Enigma",
  "findings": [
    {
      "symbol": "check_flag",
      "address": "0x104f8c180",
      "kind": "comparison_site",
      "note": "cmp x20, x0 -- real pass/fail gate #1",
      "suggested_action": "watch x20,x0; patch x20 if mismatch"
    }
  ]
}

`symbol` and `address` are both optional per finding, but at least one
must be present. `symbol` is preferred when present (matches existing
`breakpoint set --name` recipes, auto-handles ASLR). `address` is
treated as a file-relative address (RVA) resolved against the target's
main module via SBModule.ResolveFileAddress() -- NOT a raw runtime/
load address captured from some prior run, which would be wrong the
moment ASLR picks a different slide.
"""

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    symbol: str = ""
    address: str = ""          # hex string, e.g. "0x104f8c180" -- file-relative
    kind: str = ""
    note: str = ""
    suggested_action: str = ""


@dataclass
class FindingsSet:
    target: str = ""
    platform: str = ""
    binary: str = ""
    findings: list = field(default_factory=list)  # list[Finding]
    source_path: str = ""


class FindingsLoadError(Exception):
    """Raised for a malformed or unreadable findings-JSON file."""
    pass


def load_findings(path: str) -> FindingsSet:
    """
    Parse a findings-JSON file into a FindingsSet. Raises
    FindingsLoadError with a specific, actionable message for anything
    malformed -- missing required fields, a finding with neither
    symbol nor address, invalid JSON -- rather than letting a cryptic
    KeyError/JSONDecodeError surface to the lldb console.
    """
    try:
        with open(path, "r") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise FindingsLoadError(f"File not found: {path}")
    except json.JSONDecodeError as e:
        raise FindingsLoadError(f"Invalid JSON in {path}: {e}")

    if not isinstance(raw, dict):
        raise FindingsLoadError(f"{path}: top-level JSON must be an object")

    raw_findings = raw.get("findings")
    if not isinstance(raw_findings, list) or not raw_findings:
        raise FindingsLoadError(f"{path}: 'findings' must be a non-empty list")

    findings_list = []
    for i, entry in enumerate(raw_findings):
        if not isinstance(entry, dict):
            raise FindingsLoadError(f"{path}: findings[{i}] must be an object")
        symbol = entry.get("symbol", "")
        address = entry.get("address", "")
        if not symbol and not address:
            raise FindingsLoadError(
                f"{path}: findings[{i}] has neither 'symbol' nor 'address' -- "
                f"at least one is required to set a breakpoint"
            )
        findings_list.append(Finding(
            symbol=symbol,
            address=address,
            kind=entry.get("kind", ""),
            note=entry.get("note", ""),
            suggested_action=entry.get("suggested_action", ""),
        ))

    return FindingsSet(
        target=raw.get("target", ""),
        platform=raw.get("platform", ""),
        binary=raw.get("binary", ""),
        findings=findings_list,
        source_path=path,
    )


# --- Active-findings registry -----------------------------------------
# Maps breakpoint ID -> Finding for whichever findings-JSON is currently
# loaded. Populated by MACELoadFindings (stop_hook.py) when a finding's
# breakpoint successfully resolves; read by _annotate_finding
# (lldb_session.py) on every stop to look up whether the current stop's
# breakpoint matches a loaded finding. Module-level, matching the
# existing WATCH_REGS pattern elsewhere in this codebase.
_active_findings: dict[int, Finding] = {}


def register_finding(breakpoint_id: int, finding: Finding) -> None:
    _active_findings[breakpoint_id] = finding


def get_finding_for_breakpoint(breakpoint_id: int) -> Optional[Finding]:
    return _active_findings.get(breakpoint_id)


def clear_findings() -> None:
    _active_findings.clear()
