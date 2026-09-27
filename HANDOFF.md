# MACE — Session Handoff

Paste this file's content (or attach it) at the start of a new Claude
chat to resume MACE work with full context, without searching through
old chat history. Update this file together with Claude at the end of
every work session — it should always reflect "where things stand
right now," not a full history (that's what ROADMAP.md and BACKLOG.md
are for).

## Mandatory workflow — always follow this
CB edits all files personally via nano; Claude never edits the repo
directly. For every change:
1. Claude gives the exact text and says which file + where to add/edit.
2. CB opens the file in nano, makes the edit, saves.
3. Claude gives validation commands (grep/wc/etc) to confirm the edit
   landed correctly.
4. Only after validation passes, Claude gives the git add/commit/push
   commands.
This applies to ROADMAP.md, BACKLOG.md, docs/, source code — everything.

## Current status (as of 2026-09-27)
v2 is pinned. All three Android/cross-platform validation targets are
complete and documented in ROADMAP.md's Priority 1 section:
- Frida-0x8 (mace_patch register flip, live syscall annotation)
- libantifrida.so (target-independence proof)
- Unity/IL2CPP (SpinCube test app — full pipeline: custom Unity 6.3 LTS
  build -> Doppelglower Il2CppDumper fork -> RVA-based lldb breakpoint
  -> register read via MACE panel -> memory write patch -> confirmed
  visible on-device effect)

CB is unavailable for MACE work after 2026-09-27 until approximately
October 12 (surgery recovery) — EXCEPT October 1-4, which are open for
work if needed. v2.5 (EEA/Collatz work) is the next major milestone,
planned to start after the Oct 12 return.

## Immediate next work — v2.1 polish bucket
See BACKLOG.md's "v2.1 polish bucket (2026-09-27)" section for full
detail. Three items, roughly in order of effort:
1. Fix `get_long_help()` missing on all 7 class-based MACE commands in
   src/mace/lldb/stop_hook.py (mechanical, low-risk, high payoff —
   docstrings already exist, just aren't wired up).
2. `mace_patch_mem` — a memory-write patch command mirroring
   `mace_patch`'s guardrails (stopped-process check, read-back
   confirmation, shared audit trail with a kind: register/memory tag).
3. Per-platform connect automation — a device-prep shell script +
   a single `mace_connect_ios`/`mace_connect_android` lldb command
   per platform (NOT unified — see BACKLOG.md's 2026-09-14 "who
   performs the attach" entry for why). Would encode everything in
   docs/android-setup.md and docs/ios-setup.md into one command.

## Optional/future
- BayatGames/RedRunner (open-source Unity game, MIT-licensed) as a
  richer Unity/IL2CPP validation target once v2.1 is done — see
  BACKLOG.md's 2026-09-27 entry. Not urgent.
- Deferred GUI recommendations from a friend's review — feasibility
  assessment already done and logged in BACKLOG.md
  ("External GUI recommendations feasibility assessment"), several
  items already sequenced into the polish work above.

## Key reference docs (read these instead of re-deriving from scratch)
- docs/android-setup.md — full Android lldb-server/connect sequence,
  including the su-mode requirement, port 10500, RVA-vs-offset
  breakpoint gotcha, stray-process cleanup
- docs/ios-setup.md — equivalent for iOS/debugserver
- docs/debugging-playbook.md — accumulated RE technique/judgment rules
- ROADMAP.md — current priority sequencing
- BACKLOG.md — parked research threads, feasibility assessments,
  architecture ideas (chronological, search by date or keyword)

## Repo
github.com/cb90999/MACE
