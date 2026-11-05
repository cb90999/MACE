"""
MACE - Mobile AArch64 Context Extension
orchestrator/gate.py

Interactive y/n confirm gate for MACE's three write-tier MCP tools
(mace_patch, mace_set_breakpoint, mace_step_instruction). Wired as a
PreToolUse hook in run.py, scoped to exactly those three tool names via
HookMatcher -- gate_write_tools itself doesn't need to re-check the tool
name for that reason, but does so defensively in case the matcher wiring
in run.py ever changes.

Field names (tool_name, tool_input on the hook input; hookEventName,
permissionDecision, permissionDecisionReason on the output) confirmed
against claude_agent_sdk 0.2.178's actual TypedDict definitions via
direct introspection, not just the README.
"""

import asyncio
import json

WRITE_TOOLS = {
    "mcp__mace__mace_patch",
    "mcp__mace__mace_set_breakpoint",
    "mcp__mace__mace_step_instruction",
    "mcp__mace__mace_continue",
}


async def gate_write_tools(input_data, tool_use_id, context):
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name not in WRITE_TOOLS:
        # Shouldn't happen given the HookMatcher wiring in run.py, but
        # fail open rather than silently blocking something unexpected.
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    summary = json.dumps(tool_input)
    prompt = f"\n[MACE] approve write call {tool_name} {summary}? [y/N] "
    answer = await asyncio.to_thread(input, prompt)

    if answer.strip().lower() == "y":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Denied by operator at MACE orchestrator gate",
        }
    }
