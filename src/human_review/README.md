# M5 — Human Review + Audit Log

**Status: not implemented.** This folder is a scaffold placeholder only —
`__init__.py` exists so it can be imported once real code lands here.

## Intended input
CLI text plus the validation reports from
`src/guardrail/post_render/` and `src/guardrail/semantic/`.

## Intended output
Either approved CLI (logged, ready to hand off for optional manual
EVE-NG testing per CLAUDE.md §1) or rejected CLI with reviewer feedback.

## Responsibility
Diff viewer, RBAC-gated approval, and an audit log recording who
approved what and when. Per CLAUDE.md §1 (core principle #4), this step
is **mandatory and must never be bypassable**, including in test/dev
mode — any future `--test-mode` bypass must be an explicit, logged flag,
never the default behavior. The reviewer role must be distinct from the
intent-creator role — this module is the last trust boundary before a
config is considered "final" in this pipeline's scope (there is no
auto-deployment after this — see CLAUDE.md §1).

## Why it doesn't exist yet
Nothing upstream of it (M2 real parser, post-render guardrail, semantic
validation) exists yet either, so there is no real validated CLI +
report pair for a human to review yet. Building an approval UI/flow
before there's real content to approve would be premature.

## Interface `pipeline.py` will call once built
```python
# src/human_review/approval_flow.py (future)
def submit_for_review(cli_text: str, reports: list, reviewer_id: str) -> ApprovalResult:
    ...
```
`pipeline.py`'s `run_pipeline()` would call this as the final step,
after semantic validation passes, and `PipelineResult` would need a new
field/status distinguishing "awaiting review" from "approved" from
"rejected by reviewer".
