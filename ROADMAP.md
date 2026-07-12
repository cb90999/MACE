# MACE Roadmap

## v0 — macOS Scaffolding (COMPLETE)
- ContextSnapshot dataclass
- GEF-like context panel with ANSI color
- LLDBSession SBFrame bridge
- stop hook — mace_on / mace_off
- trace mode — mace_trace_on / mace_trace_off
- .lldbinit auto-loader
- Validated against EEA binary (debug + stripped)
- 5 target binaries: debug, stripped, obf_debug, obf_stripped, obf_hardened

## v0.1 — macOS Polish
- wN display alongside xN when upper 32 bits are zero
- ASLR slide calculation — automatic base address handling
- Terminal width auto-detection
- pyproject.toml — proper package installation
- Validate trace mode against obfuscated + hardened EEA binary

## v1 — iOS (headline target)
- debugserver workflow on palera1n iPad (iOS 18.7.2, A10, PAC-free)
- MASTG iOS UnCrackable Level 1-3
- objc_msgSend interception and annotation
- Syscall annotation (svc #0x80 + x16)
- Hardware breakpoint mode for hardened targets
- README "When to Use MACE" section

## v2 — Android
- lldb-server on Pixel 10a (Android 16, Tensor G4)
- MASTG Android targets
- Syscall annotation (svc #0 + x8)
- PAC-aware pointer display
- libantifrida.so as validation target
- Flutter/Dart AOT analysis

## v3 — AI + MCP (NowSecure demo target)
- MCP server — mace_get_register_context, mace_set_breakpoint,
  mace_read_memory, mace_get_backtrace, mace_step_instruction
- DSPy routing — local/cloud hybrid
- Telemetry opt-out by default
- SSE server mode for remote debugging
- NowSecure webinar demo — October/November
