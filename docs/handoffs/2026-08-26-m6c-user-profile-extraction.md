# Session Handoff

## Completed

- Milestone slice `M6c` completed: optional, off-by-default, cross-project
  user-profile extraction -- the last unstarted item on
  `docs/IMPLEMENTATION_PLAN.md`, so `M6: Personal workflow features` is now
  fully done.
- `src/mythinking/state.py`: new `UserProfile` (`role`, `expertise`,
  `working_style`, `updated_at` -- deliberately narrow, no free-form notes
  field, so it can't become a dumping ground), `UserProfileUpdate` (partial
  update draft), `ProfileAnalysis` (structured extractor output); `SessionGraphState`
  gained `profile_analysis`
- `src/mythinking/profile.py` (new): `ProfileService.merge(...)` -- sets
  `role` when non-blank, appends unique `expertise`/`working_style` entries,
  same shape as `PlanningService.merge`; `format_profile(...)` -- renders the
  profile as a readable block for `mythinking profile`, deliberately **not**
  yet wired into the supervisor prompt (see Decisions locked)
- `src/mythinking/agents/profile_extractor.py` (new): `ProfileExtractor`
  specialist, structurally identical to `Planner`/`Researcher` -- calls the
  `profile_extractor` prompt with `user_profile` + `user_message`, returns a
  validated `ProfileAnalysis`
- `prompts/profile_extractor.v1.yaml` (new): instructs extraction of only
  explicitly-stated, low-sensitivity, cross-project facts (role, expertise,
  working-style preferences) and a hard exclusion list for sensitive personal
  categories (health, relationships, finances, politics/religion, legal
  status) even if the user states them outright; cites Anthropic's context-
  engineering guidance (keep persisted context minimal/curated) and GDPR
  Art. 5's data-minimization principle
- `src/mythinking/persistence.py`: new `ProfileRepository` -- a `user_profile`
  table in the same sqlite file as `StateRepository`, holding a single
  singleton row (`load()` returns an empty `UserProfile()` when nothing is
  saved yet; `save()` upserts)
- `src/mythinking/config.py`: new `Settings.enable_profile_extraction: bool`
  (default `False`, env `MYTHINKING_ENABLE_PROFILE_EXTRACTION`) -- the
  off-by-default toggle
- `src/mythinking/graph.py`: new `extract_profile` node, wired
  `extract_evidence -> extract_profile -> choose_mode`, i.e. the same linear,
  frame-path-only placement `extract_evidence` already has (it does not run
  on the explore/converge/research/plan/branch-handled routes, matching that
  existing precedent rather than inventing new coverage rules). No-ops (skips
  its LLM call and persistence entirely) when `profile_extractor` or
  `profile_repository` is `None`. `build_thinking_graph(...)` gained
  `profile_extractor`, `profile_repository`, `profile_service` optional
  parameters
- `src/mythinking/runtime.py`: `ThinkingRuntime` gained `profile_extractor`
  and `profile_repository` parameters; `profile_repository` always
  default-constructs (cheap, no model calls); `profile_extractor` stays
  `None` unless explicitly injected *or* `settings.enable_profile_extraction`
  is `True` -- this is the actual off/on switch. New `get_user_profile()`
  accessor
- `src/mythinking/cli.py`: new `mythinking profile` command (prints whether
  extraction is enabled, then the current profile via `format_profile`);
  `mythinking status` now also reports `Profile extraction enabled: ...`
- `evals/cases.jsonl`: added `profile-mixed-sensitivity` (category
  `profile_extraction`) -- a message mixing a stated role with a sensitive
  personal detail, expecting only the role to be recorded. This is the same
  spirit as the pre-existing `memory-sensitive` eval case
  (`category: memory_policy`), which had already anticipated this slice
- `README.md`: documented `mythinking profile` and
  `MYTHINKING_ENABLE_PROFILE_EXTRACTION`
- Tests added: `tests/test_profile.py` (new, mirrors `tests/test_planning.py`),
  `tests/test_persistence.py` (`ProfileRepository` round-trip/empty/overwrite),
  `tests/test_config.py` (default-off, enable-via-field), `tests/test_graph.py`
  (`extract_profile` runs and persists with an extractor, no-ops without one),
  `tests/test_runtime.py` (off-by-default, auto-construction when enabled,
  extraction+persistence during `run_turn`), `tests/test_cli.py` (`profile`
  command parsing, disabled/empty output, populated output), `tests/test_prompts.py`
  (registry loads `profile_extractor:v1`)
- Commands run:
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run pytest` (173 passed, up from 156)
  - Manual smoke test: `MYTHINKING_ENABLE_PROFILE_EXTRACTION=true uv run
    mythinking chat "I'm a backend engineer moving into ML, and by the way
    I'm going through a divorce right now so I'm a bit distracted. ..."`
    against the real configured OpenRouter model, then `mythinking profile`
    -- captured `Role: backend engineer` only; the divorce detail was
    correctly never recorded. Also verified `mythinking status`/`mythinking
    profile` report the disabled state correctly when the env var is unset.

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- **Profile is not yet threaded into the supervisor prompt or response
  generation.** This was a deliberate scope cut, not an oversight: wiring it
  in would mean a new `SupervisorAgent.respond(...)` parameter, a
  `lead_partner` prompt version bump, and touching the large `FakeSupervisor`/
  `RecordingSupervisor` fixtures across `test_graph.py`/`test_runtime.py`/
  `test_supervisor.py` -- the same blast radius M6b accepted for
  `planner_analysis`. `format_profile(...)` already exists and is tested, so
  that follow-up slice is just plumbing, not new design.
- Extraction runs unconditionally on every turn that takes the frame path
  once enabled -- there is no per-turn opt-in or explicit-request trigger
  (unlike `Planner`/`Researcher`). This matches the plan's framing
  ("automatic, off by default") rather than the M6b-style explicit-request
  pattern, since asking the user to explicitly request "please learn about
  me" on every turn would defeat the point of ambient profile-building.
- The safety property lives entirely in the prompt (an explicit exclusion
  list for sensitive personal categories, evaluated with
  `profile-mixed-sensitivity`), not in code. There is no code-level filter or
  keyword blocklist on `UserProfileUpdate` fields -- the schema itself is
  narrow (only `role`/`expertise`/`working_style`, no free-text notes field),
  which structurally limits what could leak through even if the prompt
  failed.
- `UserProfile` is a singleton (one row, fixed id), not scoped per-project or
  per-user -- consistent with this being a personal, single-user local tool
  (same framing already used for "no auth on the API").
- `ProfileRepository` reuses `Settings.state_database_path` (same sqlite
  file as project state, new table) rather than a new `Settings` field for a
  separate path -- one local data file for a single-user tool, same
  discipline as the CORS-origins decision in the M7c handoff.

## Open issues

- Profile is extracted and persisted but never read back into a turn's
  response. The natural next step (deferred here) is threading
  `format_profile(...)` into `SupervisorAgent.respond(...)` and
  `prompts/lead_partner.vN.yaml`.
- No API surface for the profile (`GET /profile` or similar) -- `M7`'s API
  layer predates this slice and wasn't touched; the frontend has no way to
  show it. CLI-only for now (`mythinking profile`).
- No way to edit or delete a captured profile fact short of directly editing
  the sqlite row -- there's no `mythinking profile forget` or similar. Given
  the schema is narrow and the extractor is conservative, this was judged
  low-risk to defer, but it's a real gap for a feature whose whole premise is
  user-controllable durable memory (the `memory-sensitive` eval case's
  "editable memory" expectation is only partially met: it's inspectable via
  `mythinking profile`, not editable).
- Only `role`/`expertise`/`working_style` are captured. If a future slice
  wants more (e.g. stated goals across projects, preferred explanation
  depth), that's a new, separately-designed field, not implied by this one.

## Next best task

- Thread the user profile into the supervisor's response context (see
  Decisions locked) -- the smallest high-value follow-up, since extraction
  without any effect on the assistant's behavior is only half the feature.
- Alternatively: a `mythinking profile forget <field>` command (or `--clear`)
  to close the "editable memory" gap noted above.
- `M6`/`M7` are both now fully done; per `docs/IMPLEMENTATION_PLAN.md` there
  is no next milestone defined beyond these. A new milestone would need
  scoping from scratch.
