"""
MACE - Mobile AArch64 Context Extension
orchestrator/mcp_client.py

Thin synchronous client for the lldb-side MCP channel (mace/mcp/channel.py).
Same Unix-socket, newline-delimited-JSON protocol used by every manual
test call this session: connect, send one JSON line, do a single recv,
close. Deliberately not a read-until-close loop -- the channel doesn't
necessarily close the connection after responding, so looping on recv()
could hang waiting for EOF that never comes. This mirrors the exact
pattern already proven live against mace_patch, mace_set_breakpoint, etc.

Synchronous (plain blocking socket I/O) by design -- callers in tools.py
run it off the asyncio event loop via asyncio.to_thread, rather than
reimplementing the protocol with an async socket library.
"""

import json
import os
import socket

SOCKET_PATH = os.environ.get("MACE_MCP_SOCKET", "/tmp/mace_mcp.sock")
RECV_BUFFER = 65536
TIMEOUT_SECONDS = 15

# mace_continue can legitimately block server-side for as long as its
# own timeout_seconds allows (default 30, hard cap
# MAX_CONTINUE_TIMEOUT=120 in channel.py). The client socket's timeout
# must cover that plus a margin, or it gives up before the server
# responds -- found 2026-11-05 (BACKLOG.md): a client-side timeout
# shorter than the server's wait caused an unhandled BrokenPipeError
# server-side and a confusing "Connection refused" on the next call.
CONTINUE_TIMEOUT_MARGIN_SECONDS = 10
DEFAULT_CONTINUE_TIMEOUT_SECONDS = 30


def send_request(tool_name: str, args: dict) -> dict:
    """Send one {"tool": ..., "args": ...} request to the channel and
    return the parsed JSON response. Raises OSError/socket.timeout on a
    transport-level failure (socket not there, channel not running,
    etc). An application-level error from channel.py (e.g. 'process is
    not stopped') comes back as a normal {"ok": false, "error": ...}
    dict, not an exception, so the agent can read and react to it."""
    request = json.dumps({"tool": tool_name, "args": args}) + "\n"

    if tool_name == "mace_continue":
        requested = args.get("timeout_seconds", DEFAULT_CONTINUE_TIMEOUT_SECONDS)
        sock_timeout = requested + CONTINUE_TIMEOUT_MARGIN_SECONDS
    else:
        sock_timeout = TIMEOUT_SECONDS

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(sock_timeout)
    try:
        sock.connect(SOCKET_PATH)
        sock.sendall(request.encode())
        raw = sock.recv(RECV_BUFFER)
    finally:
        sock.close()

    if not raw:
        return {"ok": False, "error": "empty response from mace_mcp channel"}
    return json.loads(raw)
