# M1 — Intent Interface

**Status: not implemented.** This folder is a scaffold placeholder only —
`__init__.py` exists so it can be imported once real code lands here.

## Intended input
A raw natural-language string plus request metadata: user id, timestamp,
session id. Comes directly from whatever front-end (CLI prompt, web form,
chat) collects the operator's request.

## Intended output
A raw intent payload (untouched text + metadata) forwarded to
`src/intent_parser/` (M2). No parsing, no interpretation of the text itself
happens here.

## Responsibility
Capture the request, do basic input normalization/sanitization (encoding,
length limits — NOT security validation, that starts at M2's schema
validation), and append the request to an audit-style request log before
forwarding it onward. This module must never trust or interpret the
content of the text — that is exclusively M2's job.

## Why it doesn't exist yet
Today, `run_pipeline()` (`src/pipeline.py`) is called directly with
hand-crafted `(task, parameters)` dicts from `tests/` and
`examples/run_demo.py` — there is no real end-to-end entry point yet
because there is no real Intent Parser (M2) to receive its output.
Building M1 before M2 exists would just be a text-capture stub with
nothing meaningful to forward to.

## Interface `pipeline.py` will call once built
```python
# src/intent_interface/interface.py (future)
def capture_intent(raw_text: str, user: str, session_id: str) -> RawIntentPayload:
    ...
```
`pipeline.py` (or a future `run_pipeline_from_request()` wrapper) would
call this first, then hand `RawIntentPayload` to M2's parser.
