# 1. The Narrator turns thinking off with `between_tools` and keeps a server-side fallback

Date: 2026-11-20 · Status: accepted · Issue: #54

## Context

The MVP spec (#17) asks the Narrator for "a single Claude Sonnet call" with "thinking off". The
call goes to `claude-sonnet-5-5`.

- On this model `thinking: {"type": "disabled"}` is rejected with a 400. The documented way to turn
  thinking off is `{"type": "between_tools"}`. The docs call it the lowest thinking setting: "the
  model does no extended thinking", and only the short notes it writes between tool calls come back
  as `thinking` blocks. The Narrator's call has no tools. We infer that it produces no thinking
  blocks and bills no thinking tokens; the docs don't state that case outright. `between_tools` is
  accepted only at effort `high` or below, takes no other field in `thinking`, and only Sonnet 5.5
  accepts it.
- The same call sends `fallbacks: "default"` under the `server-side-fallback-2026-07-01` beta. When
  Sonnet 5.5 declines (`stop_reason: "refusal"`) in the `cyber` or `frontier_llm` category, the API
  retries the request on Claude Sonnet 5 within the same HTTP call. Declines in its other categories
  (`bio`, `reasoning_extraction`, `general_harms`) are not retried. Under this beta version a
  `between_tools` request that falls back runs on Sonnet 5 with thinking disabled.

## Decision

- Keep `thinking: {"type": "between_tools"}` and send no effort, so it stays at its default
  (`high`). This is "thinking off" on this model.
- Keep `fallbacks: "default"` as cheap insurance. It still counts as one Claude call: the
  application makes one request and gets one response, and thinking stays off on the fallback
  model. Astronomy narration should rarely trip a `cyber` or `frontier_llm` classifier. When one
  does, though (a false positive), the fallback turns what would have been a `NarrationError`, a
  retry and probably a `502 narration_failed` into a normal Cosmic Report. It costs nothing when it
  doesn't fire.

## Consequences

- Now and then a Cosmic Report may be written by Claude Sonnet 5 instead of Claude Sonnet 5.5, in
  the same voice and under the same structured-output schema. That departs from #17's "use the
  current Sonnet model id" for that one report.
- Refusals in the categories the fallback doesn't cover still end in a `NarrationError`.
- Moving to another model means revisiting both settings. `between_tools` is a 400 on every model
  except Sonnet 5.5. The fallback's reach depends on the model too: for Sonnet 5.5 the only fallback
  model is Claude Sonnet 5. Raising effort above `high` is a 400 while `between_tools` is set.
