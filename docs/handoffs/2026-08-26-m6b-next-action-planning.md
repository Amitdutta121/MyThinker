# Session Handoff

## Completed

- Milestone slice `M6b` completed: next-action planning (second slice of
  `M6: Personal workflow features`)
- `src/mythinking/state.py`: added `PlanTrigger` (`NONE`/`EXPLICIT_REQUEST`),
  `NextActionDraft` (description, success_signal, failure_signal,
  time_box_minutes, implementation_intention), `PlanIntent` (deterministic
  classification, same shape as `ResearchIntent`), `PlannerAnalysis`
  (summary, next_actions_to_add); `SessionGraphState` gained `plan_intent`
  and `planner_analysis` fields
- `src/mythinking/planning.py` (new): `PlannerRouter.detect(...)` -- phrase-list
  classifier for an explicit "what should I do next / plan next steps" request,
  same shape as `ResearchRouter`; `PlanningService.merge(...)` -- appends
  `NextActionDraft` entries into `ProjectState.next_actions`, deduping by
  normalized `description` (no linked-task concept needed, unlike
  `ResearchImporter`); `format_next_actions(...)` -- renders open (not
  `completed`) next actions for the supervisor prompt, same shape as
  `format_open_research_tasks`
- `src/mythinking/agents/planner.py` (new): `Planner` specialist, structurally
  identical to `Researcher`/`Synthesizer` -- calls the `planner` prompt with
  `project_state` + `user_message`, returns a validated `PlannerAnalysis`
- `prompts/planner.v1.yaml` (new): instructs 1-3 grounded, time-boxed next
  actions, each with an if-then `implementation_intention`, presented as
  candidates, never invented goals; evidence cites the Gollwitzer & Sheeran
  implementation-intentions meta-analysis and Locke & Latham goal-setting
  theory (`https://pubmed.ncbi.nlm.nih.gov/12237980/`)
- `prompts/lead_partner.v7.yaml` (new): adds `next_actions_plan` and
  `planner_analysis` context blocks plus a collaboration rule; is now the
  latest `lead_partner` version and is selected automatically by
  `PromptRegistry.get("lead_partner")` (no code default changed)
- `src/mythinking/agents/supervisor.py`: `SupervisorAgent.respond(...)` gained
  a `planner_analysis: PlannerAnalysis | None = None` parameter (appended,
  9th positional); renders `next_actions_plan` (via `format_next_actions`) and
  `planner_analysis` into the prompt; added a `ThinkingMode.DECIDE` default
  question fallback ("Does this next action work, or should we plan something
  else?") mirroring the existing CONVERGE/RESEARCH fallbacks
- `src/mythinking/graph.py`: new `route_planning` and `plan` nodes, wired
  after `route_research` (`route_research` -> `{research, route_planning}`;
  `route_planning` -> `{plan, frame}`; `plan` -> `choose_mode`), same pattern
  as the explore/converge and research routes; `choose_mode(...)` gained a
  `plan_intent` parameter and returns `ThinkingMode.DECIDE` for an explicit
  plan request -- this is the first owner of `DECIDE`, which had been unused
  since M4; `build_thinking_graph(...)` gained `planner`, `planner_router`,
  `planning_service` optional parameters (defaults constructed like the other
  optional specialists/services)
- `src/mythinking/runtime.py`: `ThinkingRuntime` gained a `planner: Planner |
  None = None` parameter, default-constructed like the other specialists, and
  passed into `build_thinking_graph(...)`
- `evals/cases.jsonl`: added `plan-next-action-request`
  (category `next_action_planning`)
- Tests added/updated: `tests/test_planning.py` (new -- router/service/format
  coverage, mirrors `tests/test_research.py`), `tests/test_graph.py` (new
  `FakePlanner`, `choose_mode` DECIDE case, routing test with a planner,
  skip-without-a-planner test; `FakeSupervisor.respond` updated for the new
  parameter), `tests/test_runtime.py` (new `StubPlanner`, a
  `run_turn`-level DECIDE test; `RecordingSupervisor.respond` and
  `_build_runtime` updated for the new parameter), `tests/test_supervisor.py`
  (next_actions_plan rendering test, DECIDE default-question test),
  `tests/test_prompts.py` (latest `lead_partner` version bumped to 7; the
  render-required-variables fixture context updated with the two new keys)
- Commands run:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pytest` (132 passed, up from 119)

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- `M6b` ships only the explicit-request trigger path (mirrors
  `ResearchRouter`/`Researcher` exactly). The M6a handoff's "likely shape"
  note also floated triggering planning automatically as part of `CONVERGE`
  once a decision is reached -- deliberately deferred; not part of this
  slice's frozen interface. If wanted later, it would mean threading a
  `Planner` call into `_converge_node` in `graph.py`.
- `ThinkingMode.DECIDE` is now owned by explicit next-action planning
  requests. This was an open issue carried since M4/M5/M6a ("DECIDE has no
  owner"); resolving it this way keeps `NextAction`/`Planner` semantically
  distinct from `CONVERGE` (choosing among alternatives) and from
  `Decision`/`ProjectState.decisions` (still unpopulated by anything -- see
  Open issues).
- `PlanningService.merge` has no equivalent to `ResearchImporter`'s
  task-linking step -- `NextAction` has no concept of "the request that
  produced it," so dedup is purely by normalized `description` against
  existing `ProjectState.next_actions`.

## Open issues

- `ProjectState.decisions` (the `Decision` model) is still never populated by
  anything -- no specialist or service writes to it. This predates M6b and is
  out of scope for it; a future slice would need to decide whether `DECIDE`
  mode should also record a `Decision`, or whether that stays a distinct,
  still-unowned concern.
- The CONVERGE-triggers-planning-automatically shape from the M6a handoff note
  was not implemented (see Decisions locked above).
- `M6c` (optional user profile extraction) is not started.
- README.md was not touched -- M6b adds no new CLI surface (planning is
  reached the same way research/explore/converge are, through
  `mythinking chat`), so there was nothing CLI-facing to document. The
  "Current runnable flow" section in README.md was already stale before this
  session (still describes the M1/M2a flow) and was left as-is, consistent
  with M4/M5 not touching it either.

## Next best task

- Start milestone slice `M6c`: optional user profile extraction, off by
  default, per `docs/IMPLEMENTATION_PLAN.md`. No interface has been frozen
  for it yet -- needs a design pass on what "profile" fields are worth
  extracting, where they'd be stored (a new `ProjectState`-adjacent model or
  something project-independent, since a profile is inherently
  cross-project), and how the off-by-default toggle should work
  (`Settings` flag vs. explicit per-turn opt-in) before implementation.
