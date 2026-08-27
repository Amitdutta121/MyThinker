# M10 — single-agent Thinker (architecture pivot)

Active branch for the session: `single-agent-thinker` (cut from
`m2-drift-control-foundation` after committing M6c/M8/M9 as `1314aa0`).

## Completed

Collapsed the multi-agent LangGraph orchestration into one
`langchain.agents.create_agent` loop, validated first in
`notebooks/thinker_final_architecture_validation (1).ipynb`.

New modules:

- `src/mythinking/agent.py` — `build_thinker`: the single `create_agent` with a
  `wrap_model_call` middleware that appends the authoritative status block, a
  `ModelCallLimitMiddleware(run_limit=10)`, and `ModelRetryMiddleware`.
- `src/mythinking/gates.py` — `NorthStarGate` / `DecisionGate` / `EvidenceGate`
  structured-output checks + regex `user_authorized_commitment`.
- `src/mythinking/board.py` — `MutableStateHolder`, `derive_mode` (display-only),
  `mark_plan_stale`, `apply_frame_analysis` (moved from the retired graph).
- `evals/runner.py` — feeds `cases.jsonl` through `run_turn`, captures the tool
  trace + board delta, `--judge` scores each expectation with the model.

Changed:

- `src/mythinking/tools.py` — `build_thinking_tools`: `set_north_star`,
  `explore_ideas`, `converge_ideas`, `commit_proposed_direction`,
  `record_user_decision`, `create_or_revise_plan`, `park_branch`, `save_evidence`
  (each with a deterministic precondition under `holder.lock`, returns
  `BLOCKED: ...` and mutates nothing on failure), plus `get_project_snapshot`
  and `ingest_pdf` / `list_indexed_documents` / `search_documents`.
  `build_context_tools` now takes the holder.
- `src/mythinking/runtime.py` — `ThinkingRuntime` rebuilt around the agent; same
  public surface (`run_turn`, `stream_turn`, `get_project_state`,
  `get_user_profile`, `repository`, `store`). Profile extraction is now a
  post-turn side call. `stream_turn` emits one NODE event per tool, then TURN.
- `src/mythinking/state.py` — `DirectionProposal` + `ProjectState.proposal`;
  `NextAction.stale`; `schema_version = 2`. Removed `SessionGraphState` and the
  intent / drift / branch-command models + enums.
- `src/mythinking/context.py` — `build_compact_agent_context`.
- `prompts/lead_partner.v10.yaml` — static single-agent system prompt.
- Docs: `README.md`, `docs/IMPLEMENTATION_PLAN.md` (M10 section), `AGENTS.md`.
- `pyproject.toml` — added `pypdf`; `notebooks/` excluded from ruff.

Deleted: `graph.py`, `drift.py`, `branching.py`,
`agents/intent_classifier.py`, `agents/supervisor.py`,
`prompts/intent_classifier.v{1,2}.yaml`, `prompts/drift_judge.v1.yaml`,
`tests/test_{graph,drift,branching,intent_classifier,supervisor}.py`.

Tests: `tests/test_runtime.py` rewritten (fake agent via monkeypatched
`build_thinker`); `tests/test_tools_thinking.py` new (22 precondition tests);
`tests/test_prompts.py` updated for v10 + retired prompts; small updates to
`tests/test_tools.py` and `tests/test_api.py`. **183 passed**, `ruff check` and
`ruff format --check` clean.

Commands run: `uv run pytest`, `uv run ruff check/format`, live CLI smoke
(`mythinking chat` → set_north_star + explore_ideas → converge → commit → plan
all verified end to end against OpenRouter).

## Decisions locked

- One agent; tool selection is the router. No intent classifier, no
  `choose_mode`, no drift-detection stage, no explicit branch-switch feature.
- `ThinkingMode` is display-only, derived by `board.derive_mode` after each turn.
- Recommendation ≠ decision: `converge_ideas` writes `ProjectState.proposal`;
  `NorthStar.current_hypothesis` is set only by `commit_proposed_direction` on
  explicit user authorization, which also stales the plan and merges a matching
  branch.
- Evidence enters only via `save_evidence` (source-support + relevance gate);
  no automatic extraction.
- `schema_version = 2`; old blobs load unchanged (new fields default).

## Open issues

- `search_documents` returns chunk text without `[[doc p.N]]` page-citation
  tags (repo `DocumentChunk` has `chunk_index`, not page). Notebook doc-grounding
  cases expect the tags — add page numbers to chunks if that fidelity matters.
- `agents/researcher.py` + `researcher.v4` + `tests/test_researcher_agent.py`
  are now orphaned (web tools live directly on the main agent). Kept, not wired.
  Delete in a follow-up if it stays unused.
- `frontend/` not touched: SSE `node` values are tool names now, and the board
  gains a `proposal` field — add a "Proposed direction" cell and a follow-up.
- `evals/runner.py` makes live calls; not in CI. Run `--judge` manually against
  `cases.jsonl` (26 cases, incl. 6 new M10 invariants) as the behavioral gate.
- `ModelRetryMiddleware` uses default backoff (1s→2s) — real retries add latency.

## Next best task

Run `python evals/runner.py --judge` and triage failures. Per notebook §25, a
repeatedly-failing invariant is the signal to add a narrow deterministic guard
at that tool boundary — not to abandon the single-agent design. After that, the
`frontend/` "proposed vs committed direction" update is the highest-value slice.
