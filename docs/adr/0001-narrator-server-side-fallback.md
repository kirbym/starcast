# 1. The Narrator turns thinking off with `between_tools` and keeps a server-side fallback

Date: 2026-11-20 · Status: accepted · Issue: #54

## Context

The MVP spec (#17) asks the Narrator for "a single Claude Sonnet call" with "thinking off". The
call goes to `claude-sonnet-5-5`.

- On this model `thinking: {"type": "disabled"}` is rejected with a 400. The documented way to turn
  thinking off is `{"type": "between_tools"}`: the model does no extended thinking and only writes
  short notes between tool calls. The Narrator's call has no tools, so no thinking is produced or
  billed. `between_tools` is accepted only at effort `high` or below, takes no other field in
  `thinking`, and only Sonnet 5.5 accepts it.
- The same call sends `fallbacks: "default"` under the `server-side-fallback-2026-07-01` beta. When
  the model declines (`stop_reason: "refusal"`) in a category the fallback covers (`cyber`,
  `frontier_llm`), the API retries the request on Claude Sonnet 5 within the same HTTP call. Under
  this beta version a `between_tools` request that falls back runs there with thinking disabled.

## Decision

- Keep `thinking: {"type": "between_tools"}` and leave effort at its default (`high`). This is
  "thinking off" on this model.
- Keep `fallbacks: "default"`. It still counts as one Claude call: the application makes one
  request and gets one response. Thinking stays off on the fallback model. Without the fallback, a
  refusal on benign astronomy text would become a `NarrationError`, then a retry, then a
  `502 narration_failed`.

## Consequences

- A small share of Cosmic Reports may be written by Claude Sonnet 5 instead of Claude Sonnet 5.5,
  in the same voice and under the same structured-output schema.
- Moving to another model means revisiting both settings: `between_tools` is a 400 on every model
  except Sonnet 5.5, and the fallback models differ per model. Raising effort above `high` is a
  400 while `between_tools` is set.
