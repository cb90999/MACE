"""
MACE - Mobile AArch64 Context Extension
core/patch_history.py

In-session audit trail for every register patch applied via
mace_patch, whether from a human at the lldb prompt or the MCP
channel (AI-driven). Lives in its own module, not stop_hook.py or
mcp/channel.py, specifically so both sides can import it without a
circular dependency -- stop_hook.py already imports mcp/channel.py
(step 1, 2026-11-03), so the reverse direction isn't available.
"""

_patch_history: list[dict] = []


def record_patch(entry: dict) -> None:
    """Append one patch record. Expected keys: register, old_value,
    new_value, pc, breakpoint_id, function, timestamp -- the same
    shape MACEPatch has always recorded."""
    _patch_history.append(entry)


def get_patch_history() -> list[dict]:
    return _patch_history


def clear_patch_history() -> int:
    """Clear the history, returning the number of entries removed."""
    count = len(_patch_history)
    _patch_history.clear()
    return count
