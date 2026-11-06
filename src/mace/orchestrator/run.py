"""
MACE - Mobile AArch64 Context Extension
orchestrator/run.py

Step 3: a standalone orchestrator process that drives the mace MCP
channel via the Claude Agent SDK. Connects to the same Unix socket
(mace_mcp.sock, via mcp_client.py) the manual test client has used all
session, exposes the six channel tools as one in-process SDK MCP server
("mace"), gates the three write-tier tools (mace_patch,
mace_set_breakpoint, mace_step_instruction) behind an interactive y/n
confirm (gate.py), and runs one task to completion.

Requires the dedicated .venv-orchestrator virtualenv (see
requirements.txt) and an ANTHROPIC_API_KEY in the environment -- this is
a separate process from lldb, not something lldb's own script
interpreter runs. lldb must already be stopped at a useful point with
mace_mcp_on running before this is launched.

Usage (from the repo root, with the venv activated):
    source .venv-orchestrator/bin/activate
    PYTHONPATH=src python3 -m mace.orchestrator.run "task prompt here"
"""

import asyncio
import sys

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    HookMatcher,
)

from mace.orchestrator.tools import mace_server, ALL_TOOL_NAMES
from mace.orchestrator.gate import gate_write_tools
from mace.orchestrator.model import select_model


async def run(task: str) -> None:
    options = ClaudeAgentOptions(
        model=select_model(),
        mcp_servers={"mace": mace_server},
        tools=ALL_TOOL_NAMES,
        disallowed_tools=["Bash", "Write", "Edit", "WebFetch", "WebSearch"],
        permission_mode="bypassPermissions",
        max_turns=20,
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="mcp__mace__mace_patch", hooks=[gate_write_tools]),
                HookMatcher(matcher="mcp__mace__mace_set_breakpoint", hooks=[gate_write_tools]),
                HookMatcher(matcher="mcp__mace__mace_step_instruction", hooks=[gate_write_tools]),
                HookMatcher(matcher="mcp__mace__mace_continue", hooks=[gate_write_tools]),
                HookMatcher(matcher="mcp__mace__mace_delete_breakpoint", hooks=[gate_write_tools]),
            ]
        },
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(task)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(msg, ResultMessage):
                print(f"\n[MACE orchestrator] done: {msg.subtype}, turns={msg.num_turns}")


def main():
    if len(sys.argv) < 2:
        print('usage: python3 -m mace.orchestrator.run "<task prompt>"')
        sys.exit(1)
    task = sys.argv[1]
    asyncio.run(run(task))


if __name__ == "__main__":
    main()
