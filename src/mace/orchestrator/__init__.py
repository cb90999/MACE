"""
MACE - Mobile AArch64 Context Extension
orchestrator/__init__.py

Package for MACE's v3 AI-pipeline orchestrator (step 3): a standalone
process, separate from lldb, that drives the lldb-side MCP channel
(mace/mcp/channel.py) over its Unix-socket protocol via the Claude Agent
SDK. Requires claude-agent-sdk (see requirements.txt) in a dedicated
virtualenv (.venv-orchestrator) -- not part of the core lldb extension's
dependency-free Python environment.
"""
