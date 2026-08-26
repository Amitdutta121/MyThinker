# Session Handoff

## Completed

- Milestone slice `M7b` completed: end-to-end streaming -- graph streaming
  through to an SSE feed, the second slice of the redefined `M7: Immersive UI
  layer`
- `src/mythinking/state.py`: new `TurnStreamEventType` (`node`/`turn`/`error`)
  and `TurnStreamEvent` (`type`, `node`, `mode`, `turn`, `detail`) -- the wire
  contract for one incremental event pushed while a turn streams. Placed next
  to `AssistantTurn`, which it wraps, matching how this module already holds
  the turn output contract rather than only domain state.
- `src/mythinking/runtime.py`: new `ThinkingRuntime.stream_turn(user_message,
  project_id=None) -> Iterator[TurnStreamEvent]`. Split into two functions
  deliberately: `stream_turn` itself is a plain (non-generator) function that
  validates the blank message and loads/validates `project_id` *eagerly* --
  raising `ValueError`/`KeyError` immediately, before any event is produced --
  then delegates to `_stream_graph`, a generator that opens the checkpointer,
  builds the graph (identical construction to `run_turn`), and calls
  `graph.stream(..., stream_mode="updates")`, re-emitting one `NODE` event per
  graph super-step (`{node_name: node_output}`), reading `mode` off
  `node_output["project_state"].current_mode` when a node touched project
  state, and tracking `node_output["assistant_turn"]` to yield a final `TURN`
  event once the graph completes. No changes to `graph.py` -- a compiled
  `StateGraph` already supports `.stream()` without any node/edge changes.
- `src/mythinking/api.py`: new `POST /turns/stream` route. Calls
  `runtime.stream_turn(...)` inside the same try/except as `POST /turns`
  (`KeyError` -> 404, `ValueError` -> 400) *before* constructing the
  `StreamingResponse`, relying on `stream_turn`'s eager validation so those
  status codes are still reachable (an HTTP status can't change once
  `StreamingResponse` starts sending). Response body is
  `_encode_server_sent_events`: renders each `TurnStreamEvent` as one
  `data: <json>\n\n` frame; if the underlying iterator raises *after*
  streaming has started (e.g. a specialist's LLM call fails mid-turn), the
  broad `except Exception` converts it into a terminal `ERROR` event instead
  of a silently truncated connection -- this is the one place in the API
  layer with a broad catch, and it's deliberate: it's the only place where an
  HTTP status is no longer available as an error channel.
- Tests added: `tests/test_runtime.py` (`test_stream_turn_emits_node_events_and_a_final_turn_event`,
  `test_stream_turn_reports_current_mode_on_choose_mode_event`,
  `test_stream_turn_rejects_blank_message_before_yielding`,
  `test_stream_turn_rejects_unknown_project_id_before_yielding`),
  `tests/test_api.py` (`FakeRuntime.stream_turn` added alongside `run_turn`;
  four new tests covering the node/turn event sequence over SSE, blank-message
  422, unknown-project 404, and the mid-stream-failure -> `ERROR` event path
  via a `FakeRuntime` whose `stream_events` is a generator that raises)
- `README.md`: documented `POST /turns/stream`, updated the foundation layout
  and "current runnable flow" sections to describe M7a+M7b instead of "M7a
  only"
- `src/mythinking/llm.py`: removed the hardcoded `route="fallback"` kwarg from
  `create_chat_model`'s `ChatOpenRouter(...)` call (see Open issues -- this was
  a pre-existing bug unrelated to streaming, fixed here because it blocked
  verifying M7b end-to-end against a real model). `tests/test_llm.py` updated
  to match.
- Commands run:
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run pytest` (154 passed, up from 146)
  - Manual smoke test: `uv run mythinking serve --port 8125` in the
    background using the project's real `.env` key, `curl -N -X POST
    .../turns/stream` with a real message -- got a well-formed SSE stream of
    11 `node` events through `capture -> ... -> choose_mode -> respond ->
    persist`, `mode` correctly reported as `"capture"` then `"clarify"` on the
    events that touched `project_state`, followed by a terminal `turn` event
    carrying the real `AssistantTurn` (mode `"clarify"`, a real generated
    message and follow-up question), then killed the process

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- SSE over WebSocket for `/turns/stream`. The handoff this session started
  from explicitly left this open. Chosen because the interaction is
  single-request/server-push-only (the client POSTs one message and reads
  events back; there's no need to push further client input on the same
  connection mid-turn), so plain HTTP streaming via `StreamingResponse` stays
  in the same request/response, testable-with-`TestClient` style as every
  other route here, with no new protocol or dependency. If M7c later needs
  bidirectional mid-turn interaction (e.g. cancel a turn, or push follow-up
  clarifications while a turn streams), that would be a reason to revisit
  WebSocket then -- not guessed at now.
- Event shape is a faithful, thin pass-through of `graph.stream(stream_mode=
  "updates")`: one `NODE` event per node the graph actually runs (including
  routing no-ops like `route_research`), not a curated subset. This matches
  the "API holds no business logic" rule from M7a -- filtering or renaming
  nodes for presentation is a frontend (M7c) concern, not this layer's.
  `mode` is populated on *any* node event whose output touched
  `project_state` (not only `choose_mode`), since that's what the node
  actually returned; only `choose_mode` changes it meaningfully, but there's
  no ambiguity or invented logic in reporting it wherever it's already true.
- No token-level LLM streaming. Every specialist (including the supervisor)
  calls `model.with_structured_output(...)`, which returns one parsed object,
  not an incremental token stream, so "streaming" here means graph-node
  progress, not partial text. This was evaluated, not assumed: token-level
  streaming would require restructuring every specialist prompt to separate a
  streamable "message" field from structured extraction fields, which is a
  prompt-contract change well beyond this slice's scope.
- `stream_turn` is split into an eager-validating outer function plus an
  inner generator (`_stream_graph`) specifically so `ValueError`/`KeyError`
  surface as normal Python exceptions at call time, before the API route
  wraps anything in `StreamingResponse`. Without this split, a generator
  function's body (including validation) wouldn't run until first iterated,
  which for `StreamingResponse` happens after the 200 status is already
  queued -- making 404/400 unreachable for streamed turns. This is the key
  design constraint this slice had to solve.

## Open issues

- **Pre-existing, unrelated bug found and fixed this session**: a real turn
  (`POST /turns` non-streaming, or `/turns/stream`) failed with
  `Chat.send() got an unexpected keyword argument 'route'`, raised from
  inside `create_chat_model` in `src/mythinking/llm.py`. Root cause: the
  installed `langchain-openrouter==0.2.8` sets `params["route"] = self.route`
  when the `route` field is non-`None` and forwards `**params` into
  `openrouter.Chat.send(...)`, but the installed `openrouter==0.11.46` SDK's
  `Chat.send()` has no `route` parameter at all (checked its signature
  directly) -- only `provider`/`models`/etc. `route: "fallback"` was
  OpenRouter's older top-level request field; the modern equivalent is
  `ProviderPreferences.allow_fallbacks`, which **defaults to `true`** (checked
  `openrouter.components.providerpreferences.ProviderPreferences`). So the fix
  was simply to delete the hardcoded `route="fallback"` kwarg from
  `create_chat_model` -- it wasn't configuring anything that isn't already the
  SDK default, and `openrouter_provider` (`data_collection`) is untouched.
  Verified with a real streamed turn against a live model (see Commands run).
  This reproduced identically on `POST /turns` (confirmed before the fix) --
  it was never caused by this session's streaming work, and the M7a handoff's
  smoke test never actually exercised a real LLM call (it only hit `/health`
  and `/projects`, which don't need one).
- No CORS configuration yet -- unchanged from M7a, still deliberately
  deferred to M7c when a separate-origin Next.js dev server exists.
- No auth on the API -- unchanged from M7a, consistent with the local-first,
  same-machine framing.
- `M6c` (optional user profile extraction) still not started, per the same
  explicit user redirection toward `M7` noted in the M7a handoff.

## Next best task

- Start milestone slice `M7c`: the Next.js immersive workspace
  (branch/evidence/decision panels, animated mode transitions driven by the
  `NODE` events' `mode` field, session selector over `GET /projects`). It can
  consume `/turns/stream` directly now that the event contract is frozen
  (`TurnStreamEvent` in `state.py`); worth deciding early whether the
  frontend renders every `NODE` event as UI (e.g. a lightweight "thinking..."
  step list) or only reacts to `mode` changes, since routing no-op nodes
  (`route_research`, etc.) carry little user-facing meaning on their own.
