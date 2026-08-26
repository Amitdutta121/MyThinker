# Session Handoff

## Completed

- Milestone `M5` completed: Researcher specialist and explicit research mode
- Added structured schemas in `src/mythinking/state.py`: `ResearchTrigger`,
  `ResearchIntent`, `ResearcherAnalysis`; extended `SessionGraphState` with
  `research_intent`, `research_analysis`
- `src/mythinking/agents/researcher.py`: model-backed `Researcher` specialist
  that answers one scoped `research_question` (an open `ResearchTask.question`
  when the request is linked to one, otherwise the raw user message), reusing
  `EvidenceDraft` for its `findings_to_add` (mirrors `EvidenceAnalyst`)
- `src/mythinking/research.py`:
  - `ResearchRouter.detect(project_state, user_message) -> ResearchIntent`:
    deterministic keyword classifier for an explicit ask to research something
    (e.g. "research this", "look into that", "can you research"); on a match,
    also looks for the best-overlap **open** `ResearchTask` (token overlap,
    same technique as `BranchSwitcher._best_matching_branch`) and records its
    id so the import step can link findings to it -- this lookup never causes
    a mode change by itself
  - `ResearchImporter.merge(project_state, research_task_id, ResearcherAnalysis) -> ProjectState`:
    appends new `EvidenceItem`s (deduped by normalized claim, same rule as
    `EvidenceLedger`), links their ids onto the matched `ResearchTask` if one
    was found, and sets that task's status to `ResearchTaskStatus.ANSWERED`
    only when `task_resolved` is true
  - `format_open_research_tasks(project_state) -> str`: renders **open**
    research tasks only, used by the supervisor prompt
- Added `route_research` and `research` graph nodes, wired after
  `route_exploration`'s `none` edge (same short-circuit pattern as M4): an
  explicit research request skips `frame`/`detect_drift`/`extract_evidence`
  and goes straight to `choose_mode`. `research` no-ops when `researcher` is
  `None`, matching the optional-specialist precedent from M3/M4
- `choose_mode` now also takes `research_intent` and returns
  `ThinkingMode.RESEARCH` for an explicit request; drift `DRIFTED` and an
  exploration intent still take priority (checked first, in that order)
- `SupervisorAgent.respond` gained one new optional parameter,
  `research_analysis` (passed through, not derived), plus two new rendered
  context values: `open_research_tasks` (always rendered, regardless of mode
  -- this is what makes a supervisor research suggestion "traceable": it can
  only name a task that is genuinely open in `project_state`) and
  `research_analysis`. Added a default RESEARCH-mode question fallback
  mirroring the CONVERGE one: "Does this research answer hold up, or should
  we keep digging?"
- Added `prompts/researcher.v1.yaml` and `prompts/lead_partner.v6.yaml`
  (latest `lead_partner` prompt is now v6; adds `open_research_tasks` and
  `research_analysis` sections plus two collaboration rules: report research
  findings as sourced evidence and state whether the question was resolved,
  and the supervisor may *suggest* researching an open task but must never
  switch into research mode itself)
- `ThinkingRuntime` wires a default `Researcher` instance, overridable via
  constructor for tests (same pattern as `explorer`/`synthesizer`); mirrors
  the existing asymmetry where the deterministic `ResearchRouter` /
  `ResearchImporter` are *not* exposed as runtime constructor params (same as
  `ExplorationRouter` / `ExplorationManager` / `ConvergenceService` before
  them) -- only model-backed specialists get that seam at the runtime layer
- Tests added/updated: `tests/test_research.py` (new), `tests/test_graph.py`,
  `tests/test_runtime.py`, `tests/test_supervisor.py`, `tests/test_prompts.py`
- Added eval case: `scoped-research-request`
- Commands run:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pytest` (103 passed)

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- Research mode is entered **only** through `ResearchRouter`'s deterministic
  explicit-request phrases -- there is no passive/keyword-overlap auto-entry
  into `ThinkingMode.RESEARCH`. Token overlap against open `ResearchTask`s is
  used solely to decide *which* open task a request's findings should be
  filed against, never to trigger the mode by itself. This satisfies the M5
  acceptance criterion ("starts only when the user asks for it or the
  supervisor makes a traceable recommendation") by keeping the recommendation
  path entirely inside the supervisor prompt (grounded in real
  `open_research_tasks` data) rather than adding a second, harder-to-audit
  deterministic trigger
- `ResearchImporter` reuses `EvidenceDraft` for `ResearcherAnalysis.findings_to_add`
  instead of introducing a parallel finding schema -- the fields are
  identical to what `EvidenceAnalyst` already produces, and evidence ledger
  writes should stay on one code path
- An unmatched/absent `research_task_id` is not an error: the Researcher can
  still answer an ad hoc question and add evidence without it being tied to
  any pre-existing `ResearchTask`
- `lead_partner` prompt version `6` is the active supervisor prompt contract

## Open issues

- `Researcher` has not been evaluated against a live model; only offline
  fixture coverage exists
- Research-request detection is deterministic-only (no model fallback judge),
  consistent with M4's explore/converge choice; can be revisited as `M5a` if
  keyword coverage proves too narrow
- No CLI/UI surface exists to list open research tasks directly; they are
  only visible via `open_research_tasks` embedded in assistant responses or
  by reading `ProjectState.research_tasks` directly
- Still no browser-backed/live research tool -- the Researcher only
  restructures information already present in the user's message or existing
  project state into typed, sourced evidence, per the M1/M3 "no external
  research tools yet" scope note
- `ThinkingMode.DECIDE` still has no owner

## Next best task

- Start milestone `M6`: Personal workflow features, per
  `docs/IMPLEMENTATION_PLAN.md`
