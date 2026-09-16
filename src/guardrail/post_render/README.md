# Post-render Syntax Guardrail

**Status: not implemented.** This folder is a scaffold placeholder only —
`__init__.py` exists so it can be imported once real code lands here.

## Intended input
Raw Cisco IOS CLI text produced by `src/config_generator/generator.py`
(M3) — i.e. runs *after* rendering, unlike the existing pre-render
guardrail (`src/guardrail/pre_render/`) which validates structured
params *before* any CLI text exists.

## Intended output
A pass/fail result + reason, same shape convention as the pre-render
checks (`(ok: bool, errors: list[str])`).

## Responsibility
Defense-in-depth: catch problems that only exist in the rendered text
itself even when the input params were clean — e.g. a bug in a `.j2`
template producing malformed syntax, or a syntax check via a Cisco
config parser (`ciscoconfparse2`) / dry-run, per CLAUDE.md §2's tech
stack. This is deliberately a *different* trust boundary than
pre-render: pre-render guardrail asks "are the params safe/valid?",
post-render guardrail asks "is the CLI that came out actually correct
and safe, independent of whether the params looked fine going in?".

## Why it doesn't exist yet
No syntax parser / dry-run integration exists in the repo yet. The
pre-render guardrail (schema + policy + context checks) was built first
because it can reject bad intent before spending any work rendering.

## TODO — deferred from this refactor
A real "intent consistency check" (params used to render vs. the
property the user actually asked for) could be designed as a proper
module here or as part of this guardrail stage later. This refactor
does **not** implement it — it only removes the previous
`validate_properties()` test-code-in-production-path violation (it was
a `guardrail/intent_validator.py` file only ever invoked by tests/demo
via an optional `expected_properties` pipeline parameter that no real
caller used). That function now lives purely in
`tests/test_intent_validator.py`.

## Interface `pipeline.py` will call once built
```python
# src/guardrail/post_render/syntax_validator.py (future)
def validate_syntax(cli_text: str) -> tuple[bool, list[str]]:
    ...
```
`pipeline.py`'s `run_pipeline()` would call this right after `render()`,
before returning `PipelineResult(status="SUCCESS", ...)` — a failure here
should map to a new explicit status rather than silently returning
`SUCCESS` with unchecked CLI.
