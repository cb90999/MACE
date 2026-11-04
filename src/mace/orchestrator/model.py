"""
MACE - Mobile AArch64 Context Extension
orchestrator/model.py

Model-selection stub for step 3. A single hardcoded constant for now --
select_model() gives run.py a stable seam to swap in real per-task-type
model selection later (e.g. a cheaper model for routine diagnostics, a
stronger one for patch/exploit analysis) without touching call sites.
"""

MODEL_NAME = "claude-sonnet-5-5"


def select_model() -> str:
    return MODEL_NAME
