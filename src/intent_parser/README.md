# M2 — Intent Parser (LLM)

**Status: not implemented — this is the single most important missing
piece for the thesis's core claim** ("LLM-based agent for secure config
generation"). Everything downstream currently only works with
hand-crafted stand-in data.

## Intended input
The raw intent payload from `src/intent_interface/` (M1) — natural
language text + metadata — plus an LLM context dict built by
`src/context_provider/builder.py::build_llm_context()` (topology info,
with `mgmt_ip` and other internal-only fields already stripped).

## Intended output
A `StructuredIntent` — the `task` + `parameters` dict — validated against
the fixed Pydantic schema in `src/schemas/intent_schema.py`
(`SupportedTask`, `CreateVlanParams`, `EnableSshParams`,
`StandardAclParams`, ...).

## Responsibility
Call the LLM using function-calling / structured output so the model is
constrained to the same schema `src/schemas/intent_schema.py` already
defines, then immediately re-validate the raw response through that
schema before anything else touches it. **Treat all LLM output as
untrusted input** — a schema-valid response is the only acceptable
output of this module; anything else must surface as
`NEEDS_CLARIFICATION`, never be silently coerced or guessed.

## Why it doesn't exist yet
Today `run_pipeline()` receives `(task, parameters)` directly from
callers (`tests/`, `examples/run_demo.py`) as a stand-in for what this
module should produce — see the module docstring in `src/pipeline.py`.
No Anthropic API call, prompt, or function-calling schema exists in the
repo yet.

## Interface `pipeline.py` will call once built
```python
# src/intent_parser/parser.py (future)
def parse_intent(raw_intent_payload, llm_context: dict) -> StructuredIntent:
    ...
```
`pipeline.py`'s `run_pipeline()` would call this first and pass its
output (`task`, `parameters`) into the existing
`classify()` (`src/guardrail/pre_render/classifier.py`) unchanged — the
pre-render guardrail step does not need to change when M2 is built.
