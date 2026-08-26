# Session Handoff

## Completed

- Milestone slice `M2b` completed: model fallback for ambiguous drift plus
  explicit user-directed branch switching / return-to-main handling
- Added `DriftJudge` and `DriftResolver` to `src/mythinking/drift.py`; the
  deterministic detector now returns `DriftStatus.AMBIGUOUS` (instead of a
  silent `on_track`) when no heuristic signal is strong enough, and the
  resolver only calls the model-backed judge for that status
- Added `BranchSwitcher` to `src/mythinking/branching.py` for deterministic
  detection and application of explicit switch / resume / return-to-main
  commands
- Extended `SessionGraphState` with `branch_command`; added a
  `handle_branch_command` graph node between `capture` and `frame` that
  short-circuits straight to `choose_mode` (skipping `frame`/`detect_drift`)
  when an explicit branch command is detected
- `SupervisorAgent.respond` now accepts `branch_command` and appends a
  deterministic confirmation line when the model omits one
- Added `prompts/drift_judge.v1.yaml` and `prompts/lead_partner.v3.yaml`
  (latest `lead_partner` prompt is now v3)
- `ThinkingRuntime` now wires a default `DriftJudge` and `BranchSwitcher`,
  both overridable via constructor for tests
- Tests added/updated: `tests/test_drift.py`, `tests/test_branching.py` (new),
  `tests/test_graph.py`, `tests/test_supervisor.py`, `tests/test_runtime.py`,
  `tests/test_prompts.py`
- Added eval cases: `ambiguous-drift-model-fallback`, `branch-switch-explicit`,
  `branch-return-main`
- Commands run:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pytest` (61 passed)

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- `DriftStatus.AMBIGUOUS` is a real terminal state the deterministic detector
  can return; it is not silently treated as `on_track`
- `DriftResolver(detector, judge).assess(...)` is the composition point: the
  judge is invoked only when the deterministic result is `AMBIGUOUS`, and an
  absent judge leaves the assessment `AMBIGUOUS` unresolved (never escalated
  to `DRIFTED` by default — a conservative, non-interrupting fallback)
- `BranchSwitcher.detect(...)` matches explicit switch/resume/return phrases
  against existing branch name+summary token overlap; ambiguous or unmatched
  phrasing returns `BranchCommandAction.NONE` and falls through to the normal
  turn flow rather than guessing
- Graph flow is now `capture -> handle_branch_command -> [frame -> detect_drift
  | (skip)] -> choose_mode -> respond -> persist`
- `lead_partner` prompt version `3` is the active supervisor prompt contract

## Open issues

- `BranchSwitcher` phrase matching is intentionally narrow (fixed trigger
  phrases); it will miss more naturally-phrased switch requests. No CLI/UI
  surface exists yet for listing branches, so a user must already know a
  branch's name to switch to it
- The `DriftJudge` fallback prompt has not been evaluated against a live
  model; only offline fixture coverage exists
- No support yet for switching to a `DISCARDED` or `MERGED` branch (by
  design, but there is no way to un-discard one)

## Next best task

- Start milestone `M3`: evidence and research ledger (evidence objects in
  state, citation-aware response formatting, offline fixtures) per
  `docs/IMPLEMENTATION_PLAN.md`
- Suggested subagent split if parallelized:
  - Subagent A: evidence schema and persistence
  - Subagent B: response formatter and citation rendering
  - Subagent C: eval cases and tests
