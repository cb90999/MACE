"""
MACE - Mobile AArch64 Context Extension
orchestrator/tools.py

SDK tool wrappers around the six MCP channel tools (mace/mcp/channel.py),
exposed to the Claude Agent SDK as one in-process MCP server ("mace").
Each wrapper is a thin pass-through: channel.py already validates args,
so this layer just forwards them over the Unix socket via mcp_client and
returns the raw JSON response as text for the agent to read.

tier/mode metadata currently lives in two places -- channel.py's _TOOLS
registry, and implicitly here via which three tool names gate.py's
WRITE_TOOLS set lists. Known duplication, acceptable for this step-3
stub; logged in BACKLOG.md.
"""

import asyncio
import json

from claude_agent_sdk import tool, create_sdk_mcp_server

from mace.orchestrator.mcp_client import send_request


@tool(
    "mace_get_register_context",
    "Get the full register context (general-purpose registers, fp/lr/sp/pc, "
    "cpsr, call chain, and MACE's annotations) of the current stopped frame.",
    {"type": "object", "properties": {}, "additionalProperties": False},
)
async def mace_get_register_context(args):
    resp = await asyncio.to_thread(send_request, "mace_get_register_context", {})
    return {"content": [{"type": "text", "text": json.dumps(resp)}]}


@tool(
    "mace_read_memory",
    "Read up to 4096 bytes of process memory at a given address, returned "
    "as a hex string.",
    {
        "type": "object",
        "properties": {
            "address": {
                "type": ["string", "integer"],
                "description": "Load address, as an int or a numeric string "
                                "('0x...' or decimal).",
            },
            "size": {
                "type": "integer",
                "description": "Number of bytes to read (max 4096).",
            },
        },
        "required": ["address", "size"],
        "additionalProperties": False,
    },
)
async def mace_read_memory(args):
    resp = await asyncio.to_thread(send_request, "mace_read_memory", {
        "address": args["address"],
        "size": args["size"],
    })
    return {"content": [{"type": "text", "text": json.dumps(resp)}]}


@tool(
    "mace_get_backtrace",
    "Get the current thread's call stack, up to max_frames (default 32, "
    "hard cap 64).",
    {
        "type": "object",
        "properties": {
            "max_frames": {
                "type": "integer",
                "description": "Maximum number of frames to return "
                                "(default 32, hard cap 64).",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
)
async def mace_get_backtrace(args):
    call_args = {}
    if "max_frames" in args:
        call_args["max_frames"] = args["max_frames"]
    resp = await asyncio.to_thread(send_request, "mace_get_backtrace", call_args)
    return {"content": [{"type": "text", "text": json.dumps(resp)}]}


@tool(
    "mace_set_breakpoint",
    "Set a breakpoint by symbol name, by symbol+offset (requires module), "
    "or by raw load address. WRITE operation -- requires operator approval.",
    {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol name."},
            "address": {
                "type": ["string", "integer"],
                "description": "Raw load address, as an int or numeric string.",
            },
            "offset": {
                "type": "integer",
                "description": "Byte offset from 'symbol'. Requires both "
                                "'symbol' and 'module'.",
            },
            "module": {
                "type": "string",
                "description": "Binary's loaded module name (e.g. "
                                "'libfoo.so'). Required if 'offset' is set.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
)
async def mace_set_breakpoint(args):
    call_args = {k: args[k] for k in ("symbol", "address", "offset", "module")
                 if k in args}
    resp = await asyncio.to_thread(send_request, "mace_set_breakpoint", call_args)
    return {"content": [{"type": "text", "text": json.dumps(resp)}]}


@tool(
    "mace_patch",
    "Patch a register to a new value at the current stopped frame. "
    "WRITE operation -- requires operator approval.",
    {
        "type": "object",
        "properties": {
            "register": {"type": "string", "description": "Register name, e.g. 'x8'."},
            "value": {
                "type": ["string", "integer"],
                "description": "New value, as an int or numeric string.",
            },
        },
        "required": ["register", "value"],
        "additionalProperties": False,
    },
)
async def mace_patch(args):
    resp = await asyncio.to_thread(send_request, "mace_patch", {
        "register": args["register"],
        "value": args["value"],
    })
    return {"content": [{"type": "text", "text": json.dumps(resp)}]}


@tool(
    "mace_step_instruction",
    "Single-step one instruction. over=false steps into calls, over=true "
    "steps over them. WRITE operation (changes execution state) -- "
    "requires operator approval.",
    {
        "type": "object",
        "properties": {
            "over": {
                "type": "boolean",
                "description": "false (default) = step-into, true = step-over.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
)
async def mace_step_instruction(args):
    call_args = {}
    if "over" in args:
        call_args["over"] = args["over"]
    resp = await asyncio.to_thread(send_request, "mace_step_instruction", call_args)
    return {"content": [{"type": "text", "text": json.dumps(resp)}]}


@tool(
    "mace_continue",
    "Resume execution and wait for the process to reach a terminal state "
    "(stopped at a breakpoint, crashed, exited, or detached), up to a "
    "timeout. WRITE operation (changes execution state) -- requires "
    "operator approval. Returns status: 'stopped'/'crashed' (with a full "
    "register-context snapshot of the new frame), 'exited' (with "
    "exit_status), 'detached', or 'timeout' if nothing happened in time.",
    {
        "type": "object",
        "properties": {
            "timeout_seconds": {
                "type": "number",
                "description": "How long to wait for a stop before giving "
                                "up (default 30, hard cap 120).",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
)
async def mace_continue(args):
    call_args = {}
    if "timeout_seconds" in args:
        call_args["timeout_seconds"] = args["timeout_seconds"]
    resp = await asyncio.to_thread(send_request, "mace_continue", call_args)
    return {"content": [{"type": "text", "text": json.dumps(resp)}]}


mace_server = create_sdk_mcp_server(
    name="mace",
    version="1.0.0",
    tools=[
        mace_get_register_context,
        mace_read_memory,
        mace_get_backtrace,
        mace_set_breakpoint,
        mace_patch,
        mace_step_instruction,
        mace_continue,
    ],
)

ALL_TOOL_NAMES = [
    "mcp__mace__mace_get_register_context",
    "mcp__mace__mace_read_memory",
    "mcp__mace__mace_get_backtrace",
    "mcp__mace__mace_set_breakpoint",
    "mcp__mace__mace_patch",
    "mcp__mace__mace_step_instruction",
    "mcp__mace__mace_continue",
]
