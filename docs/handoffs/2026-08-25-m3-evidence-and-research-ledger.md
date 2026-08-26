# Session Handoff

## Completed

- Milestone `M3` completed: evidence and research ledger
- Added `EvidenceItem`/`ResearchTask` persistence support already scaffolded
  in `ProjectState` (M1); added the missing extraction and formatting layer:
  - `EvidenceDraft`, `ResearchTaskDraft`, `EvidenceAnalysis` structured schemas
    in `src/mythinking/state.py`
  - `src/mythinking/agents/evidence_analyst.py`: model-backed specialist that
    extracts typed, sourced evidence candidates and research-task candidates
    from a user message (mirrors `FrameAnalyst`)
  - `src/mythinking/evidence.py`: `EvidenceLedger` (deterministic merge/dedupe
    into `project_state.evidence` / `project_state.research_tasks`) and
    `format_evidence_ledger(project_state)` (citation-aware formatter,
    grouped Facts / Inferences / Hypotheses, each with a source citation or
    an explicit "no source provided" marker)
- Added `extract_evidence` graph node, running after `detect_drift` and
  before `choose_mode`; skipped (no-op) when no `evidence_analyst` is
  configured, and skipped entirely for explicit branch-command turns (same
  short-circuit as `frame`/`detect_drift`)
- `SupervisorAgent.respond` now renders `format_evidence_ledger(project_state)`
  into the prompt as `evidence_ledger` (no new parameter — computed from the
  `project_state` already passed in)
- Added `prompts/evidence_analyst.v1.yaml` and `prompts/lead_partner.v4.yaml`
  (latest `lead_partner` prompt is now v4; adds the evidence-ledger section
  and an instruction to cite facts / flag hypotheses explicitly)
- `ThinkingRuntime` wires a default `EvidenceAnalyst` + `EvidenceLedger`, both
  overridable via constructor for tests
- Tests added/updated: `tests/test_evidence.py` (new), `tests/test_graph.py`,
  `tests/test_runtime.py`, `tests/test_supervisor.py`, `tests/test_prompts.py`
- Added eval cases: `evidence-fact-with-source`, `evidence-research-task`
- Commands run:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pytest` (69 passed)

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- `EvidenceLedger.merge(project_state, analysis) -> ProjectState` is the
  deterministic boundary that writes extracted evidence/research tasks into
  state; it dedupes by normalized claim/question text, mirroring the
  `_append_unique` pattern used elsewhere
- `format_evidence_ledger` is a pure function, not a stateful service, so the
  supervisor can call it directly without holding an `EvidenceLedger`
  instance
- Evidence extraction runs on every non-branch-command turn regardless of
  drift status (a drifted tangent can still carry evidence worth capturing);
  it is opt-in at the graph level (`evidence_analyst=None` skips it), matching
  the `drift_judge` precedent from M2b
- `lead_partner` prompt version `4` is the active supervisor prompt contract
- `EvidenceItem.source_url`/`source_title` remain plain strings (not a
  validated `HttpUrl`), consistent with the existing M1 schema — a user can
  cite a non-URL source (e.g. "internal changelog")

## Open issues

- `EvidenceAnalyst` extraction has not been evaluated against a live model;
  only offline fixture coverage exists
- No CLI/UI surface exists yet to list evidence or research tasks directly
  (they are visible only via the rendered `evidence_ledger` text embedded in
  assistant responses, or by reading `ProjectState.evidence` /
  `.research_tasks` directly)
- `ResearchTask.status` (open/answered/dropped) has no state-transition
  service yet — tasks are created but nothing marks them answered or dropped
- Per the plan, browser-backed research is explicitly out of scope for M3

## Next best task

- Start milestone `M4`: Explorer and Synthesizer specialists (divergent
  alternatives plus convergence into a decision-ready summary), per
  `docs/IMPLEMENTATION_PLAN.md`
- Suggested subagent split if parallelized:
  - Subagent A: explorer specialist
  - Subagent B: synthesizer specialist
  - Subagent C: routing logic and tests
