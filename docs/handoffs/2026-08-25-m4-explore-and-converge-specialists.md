# Session Handoff

## Completed

- Milestone `M4` completed: explore and converge specialists
- Added structured schemas in `src/mythinking/state.py`: `IntentAction`,
  `ExplorationIntent`, `AlternativeDraft`, `ExplorerAnalysis`,
  `ConvergenceOption`, `SynthesizerAnalysis`; extended `SessionGraphState` with
  `exploration_intent`, `exploration_analysis`, `synthesis`
- `src/mythinking/agents/explorer.py`: model-backed `Explorer` specialist that
  proposes 2-4 divergent, un-ranked alternatives (mirrors `FrameAnalyst`)
- `src/mythinking/agents/synthesizer.py`: model-backed `Synthesizer` specialist
  that compares existing branches and proposes one `recommended_choice` with
  `rationale`, referencing only branches that already exist
- `src/mythinking/exploration.py`:
  - `ExplorationRouter.detect(project_state, user_message) -> ExplorationIntent`:
    deterministic keyword classifier (explore vs. converge vs. none); checks
    converge triggers before explore triggers so a message naming both resolves
    to converge
  - `ExplorationManager.merge(project_state, ExplorerAnalysis) -> ProjectState`:
    appends new alternatives as `BranchStatus.ACTIVE` `IdeaBranch` entries,
    deduped by normalized name or summary
  - `ConvergenceService.merge(project_state, SynthesizerAnalysis) -> ProjectState`:
    matches `options_considered` to existing branches by normalized name and
    marks them `BranchStatus.MERGED`; sets `north_star.current_hypothesis` to
    `recommended_choice` when present; silently ignores unmatched branch names
  - `format_branch_alternatives(project_state) -> str`: pure formatter listing
    `ACTIVE`/`PARKED` branches (excludes `MERGED`/`DISCARDED`), used by the
    supervisor prompt
- Added `route_exploration` graph node plus `explore`/`converge` nodes; wired
  after `handle_branch_command`'s `continue` edge (same short-circuit pattern
  as branch commands): an explicit explore/converge request skips
  `frame`/`detect_drift`/`extract_evidence` entirely and goes straight to
  `choose_mode` after the explore/converge node runs. Both nodes no-op
  (pass through unchanged state) when their specialist is `None`, matching the
  optional `evidence_analyst` precedent from M3.
- `choose_mode` now takes `exploration_intent` and returns `ThinkingMode.EXPLORE`
  / `ThinkingMode.CONVERGE` for explicit requests; drift `DRIFTED` still takes
  priority over an explore/converge intent
- `SupervisorAgent.respond` gained two new optional parameters,
  `exploration_analysis` and `synthesis` (same pattern as `frame_analysis` /
  `drift_assessment` / `branch_command` -- passed through, not derived), plus
  a computed `branch_alternatives` render (same pattern as `evidence_ledger`).
  Added a default CONVERGE-mode question fallback mirroring the existing
  CHALLENGE fallback: "Does this recommended choice work, or should we keep
  comparing options?"
- Added `prompts/explorer.v1.yaml`, `prompts/synthesizer.v1.yaml`, and
  `prompts/lead_partner.v5.yaml` (latest `lead_partner` prompt is now v5; adds
  `branch_alternatives`, `exploration_analysis`, `synthesis` sections and
  collaboration rules for presenting alternatives without ranking them and
  presenting a recommendation as a suggestion, not an imposed decision; also
  dropped the stale "stay within the current M3 scope" line)
- `ThinkingRuntime` wires default `Explorer` + `Synthesizer` instances, both
  overridable via constructor for tests
- Tests added/updated: `tests/test_exploration.py` (new), `tests/test_graph.py`,
  `tests/test_runtime.py`, `tests/test_supervisor.py`, `tests/test_prompts.py`
- Added eval cases: `explore-alternatives-request`, `converge-decision-ready`
- Commands run:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pytest` (87 passed)

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- Explore/converge requests are detected deterministically (keyword phrases),
  the same architectural choice as `BranchSwitcher` and the M2a drift
  heuristics -- no model fallback judge for this classification in M4
  (unlike drift, which has `DriftJudge`); can be added later as `M4a` if
  keyword coverage proves too narrow
- Explorer-created alternatives are appended as `BranchStatus.ACTIVE` (they are
  live options on the table), distinct from tangent-preserved branches from
  drift, which are created `PARKED`
- `ConvergenceService` matches branches by exact normalized-name equality, not
  fuzzy token overlap (unlike `BranchSwitcher`'s matching) -- the Synthesizer
  prompt is instructed to echo `branch_name` exactly as it appears in
  `project_state`, so an unmatched name is treated as a prompt-following
  failure and safely ignored rather than guessed at
  - No `Decision` object is created automatically; `ConvergenceService` only
  marks branches `MERGED` and updates `north_star.current_hypothesis` --
  recording an explicit `Decision` is left for a future decide-mode milestone
- `lead_partner` prompt version `5` is the active supervisor prompt contract

## Open issues

- `Explorer`/`Synthesizer` have not been evaluated against a live model; only
  offline fixture coverage exists
- Explore/converge intent detection is deterministic-only; a genuinely
  ambiguous phrasing (e.g. "what should I do here?") will not trigger either
  mode even when the user meant one of them
- No CLI/UI surface exists to list current alternatives directly; they are
  only visible via `branch_alternatives` embedded in assistant responses or by
  reading `ProjectState.branches` directly
- `ThinkingMode.DECIDE` still has no owner; M4 only reaches `EXPLORE` and
  `CONVERGE`

## Next best task

- Start milestone `M5`: Researcher specialist and explicit research mode, per
  `docs/IMPLEMENTATION_PLAN.md`
