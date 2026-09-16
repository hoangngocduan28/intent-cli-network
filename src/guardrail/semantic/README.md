# Semantic Validation (Batfish)

**Status: not implemented.** This folder is a scaffold placeholder only —
`__init__.py` exists so it can be imported once real code lands here.

## Intended input
CLI text that has already passed `src/guardrail/post_render/` (syntax
guardrail), plus the current baseline config of the target device(s) —
needed to reason about the *effect* of applying the new CLI, not just
the new CLI in isolation.

## Intended output
A semantic validation report: conflicts found, reachability query
results, anything Batfish's offline analysis surfaces.

## Responsibility
Batfish-based offline analysis per CLAUDE.md §2 — reachability queries,
ACL conflict detection, etc. This is the check that can catch things no
amount of syntax/policy validation can: e.g. a syntactically perfect and
policy-compliant ACL that still breaks reachability for a route that
matters, because that requires reasoning about the whole network model,
not just the one CLI snippet being generated.

## Why it doesn't exist yet
No Batfish container/client integration exists in the repo yet. This is
explicitly listed as missing in the original README and CLAUDE.md's
target pipeline — it depends on M3 (renderer) and the post-render syntax
guardrail existing first, since it consumes their output.

## Interface `pipeline.py` will call once built
```python
# src/guardrail/semantic/batfish_validator.py (future)
def validate_semantics(cli_text: str, baseline_config) -> SemanticReport:
    ...
```
`pipeline.py`'s `run_pipeline()` would call this after the post-render
syntax guardrail passes, before handing off to `src/human_review/` (M5)
— the human reviewer should see this report alongside the diff, not just
the raw CLI.
