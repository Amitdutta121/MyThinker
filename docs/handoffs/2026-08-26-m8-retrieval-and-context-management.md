# Session Handoff

## Completed

- Milestone `M8` completed: retrieval, document storage, and context
  management -- a new milestone (not on the original `docs/IMPLEMENTATION_PLAN.md`
  roadmap, which stopped at `M7`), added and documented as part of this
  session since `M6`/`M7` were both already fully done. Full design is in
  `docs/IMPLEMENTATION_PLAN.md`'s new `M8` section.
- Motivation: the prototype had two live liabilities, not hypothetical ones --
  `agents/researcher.py` did a single LLM pass with no external search at
  all, and every specialist agent (`frame_analyst`, `evidence_analyst`,
  `explorer`, `synthesizer`, `planner`, `intent_classifier`, `researcher`)
  plus `supervisor.py` (redundantly, alongside its already-scoped formatters)
  sent the *entire* `ProjectState` as raw JSON into every LLM call, every
  turn -- unbounded as evidence/decisions/research tasks accumulate.
- **Storage discovery that changed the design mid-plan**: the original plan
  called for a hand-rolled `sqlite-vec` index and a custom `DocumentRepository`.
  Reading the actually-installed packages showed `langgraph-checkpoint-sqlite`
  (already a declared dependency, `>=3.0`) ships
  `langgraph.store.sqlite.SqliteStore` -- an official, already-installed,
  namespace-scoped key/value store with built-in optional sqlite-vec-backed
  vector search, and `sqlite-vec` itself is already pulled in transitively.
  The plan was revised to wrap that instead of building a new storage engine.
- `src/mythinking/documents.py` (new): `Document`/`DocumentChunk` pydantic
  models (same `new_id()`/`utc_now()` convention as `state.py`), kept **out
  of `ProjectState`** deliberately -- full research-source text stays out of
  the small JSON blob `StateRepository` persists. Plus a hand-rolled,
  dependency-free `chunk_text(text, *, max_chars=1500, overlap=200)`
  (paragraph-boundary splitting, hard-cut fallback for oversized paragraphs).
- `src/mythinking/retrieval.py` (new): a thin typed wrapper around
  `SqliteStore` -- `open_document_store(...)` (opens the store, loads the
  vector index config, runs `.setup()`), `index_document`/`index_chunk`/
  `index_content` (write), `search_content`/`list_documents`/`list_chunks`
  (read). No custom schema or SQL introduced; namespaces are
  `(project_id, content_type)` with `content_type` in
  `{"document", "document_chunk", "evidence", "research_task", "decision"}`.
- `src/mythinking/llm.py`: new `create_embeddings_model(...)` alongside
  `create_chat_model`, since `langchain-openrouter` has no embeddings class --
  `OpenAIEmbeddings` pointed at OpenRouter's OpenAI-compatible
  `/api/v1/embeddings` endpoint reuses the same API key rather than requiring
  a second provider account.
- `src/mythinking/context.py` (new): scoped, pure `format_*` functions
  (`format_north_star_brief`, `format_open_questions`, `format_parked_ideas`,
  `format_assumptions`, `format_decisions` -- the last is inert today since
  nothing writes to `ProjectState.decisions` yet, added for forward
  compatibility -- `format_project_context` for the supervisor) plus
  `ContextRetriever`, which renders the existing full-list formatter below a
  configurable item-count threshold and switches to `SqliteStore`-backed
  top-K semantic search at or above it (`select_evidence`,
  `select_research_tasks`, `select_decisions`, `select_document_chunks`).
- `src/mythinking/exploration.py`: new `format_all_branch_names(...)` --
  every branch regardless of status, distinct from the existing
  `format_branch_alternatives` (which excludes merged/discarded branches);
  needed because the Explorer/Synthesizer prompts' "don't repeat an existing
  alternative" instruction covers *all* branches, not just open ones.
- `src/mythinking/deep_research.py` (new): `DeepResearchRunner` wraps
  `gpt-researcher`'s `GPTResearcher` -- only `conduct_research()` +
  `get_research_sources()` are used (`write_report()` is skipped
  deliberately; it's an extra costly LLM pass producing markdown prose the
  typed extraction step doesn't need). `_configure_environment()` sets
  gpt-researcher's own `os.environ` variables (`OPENROUTER_API_KEY`,
  `EMBEDDING=openrouter:...`, `FAST_LLM`/`SMART_LLM`/`STRATEGIC_LLM=openrouter:...`,
  `RETRIEVER`, `TAVILY_API_KEY` when selected) immediately before
  construction, since gpt-researcher reads its config from process
  environment, not this app's `Settings` object. `asyncio.run()` bridges its
  async API into this app's fully synchronous call chain -- documented in
  code as a load-bearing assumption (correct only while `api.py` routes and
  the graph stay synchronous).
- `src/mythinking/agents/researcher.py`: internals fully replaced. Public
  contract unchanged -- `analyze(project_state, user_message, research_task)
  -> ResearcherAnalysis` -- so `ResearchImporter.merge` and its `graph.py`
  call site needed no changes. New constructor dependencies:
  `context_retriever`, `deep_research_runner`, `store`. `analyze()` now runs
  deep research for the scoped question, stores+indexes the fetched sources
  as `Document`/`DocumentChunk`, retrieves the most relevant chunks plus the
  existing evidence ledger, and grounds the typed extraction call in that
  retrieved context instead of the user's message alone.
- `prompts/researcher.v2.yaml` (new): `{research_question}`,
  `{retrieved_context}`, `{existing_evidence_ledger}`, `{user_message}` --
  no more `{project_state}`.
- Context-management refactor, one new prompt version per agent, each
  grounded in that prompt's actual placeholders (not a blind strip):
  - `evidence_analyst` -> v2: `{evidence_ledger}`/`{open_research_tasks}`,
    reusing the existing formatters directly -- zero new formatter code,
    lowest-risk change in the set.
  - `explorer`/`synthesizer` -> v2: `{north_star_brief}`,
    `{all_branch_names}`, `{branch_alternatives}`.
  - `planner` -> v2: `{north_star_brief}`, `{open_questions}`,
    `{branch_alternatives}`, `{next_actions_plan}`.
  - `intent_classifier` -> v2: `{project_state}` dropped **entirely**, no
    replacement -- confirmed by reading the v1 template that no success
    criterion ever referenced a specific field; classification is driven
    purely by message wording. `IntentClassifier.classify` lost its
    `project_state` parameter (`classify(self, user_message: str)`);
    `graph.py`'s `_classify_intent_node` call site updated to match.
  - `frame_analyst` -> v2: `{north_star_brief}`, `{assumptions}`,
    `{open_questions}`.
  - `lead_partner` -> v8: raw `{project_state}` block removed, `{project_context}`
    (new `format_project_context`) added; every other placeholder was
    already scoped and is unchanged.
  - `profile_extractor.v1` and `drift_judge.v1` deliberately **left
    untouched** -- `profile_extractor` already renders only
    `user_profile`/`user_message`; `drift_judge` (`drift.py:194`) still does
    the same raw-dump pattern and is a real 8th instance of the problem, but
    it wasn't one of the seven specialist agents in scope for this
    milestone (see Open issues).
- `graph.py`: `_evidence_node`/`_research_node` now diff evidence/research
  tasks by id before vs. after their respective `merge(...)` calls and index
  only the newly-added items into the store, when one is supplied --
  `EvidenceLedger.merge`/`ResearchImporter.merge`'s tested return signature
  (`ProjectState`) is unchanged. `build_thinking_graph(...)` gained an
  optional `store: SqliteStore | None` parameter.
- `runtime.py`: `ThinkingRuntime` opens the document store once, at
  construction, only when `self.researcher is None and
  settings.enable_deep_research` (mirrors the existing
  `enable_profile_extraction` pattern exactly) -- constructing
  `create_embeddings_model(...)` unconditionally would have broken every
  existing test that constructs `ThinkingRuntime` without a real API key
  (they all inject explicit agent doubles, so `create_chat_model`/etc. were
  never actually exercised before; an unconditional embeddings-client
  construction would have been the first thing to break that). The opened
  store's underlying context-manager object is held on `self._store_cm` so
  it isn't garbage-collected mid-process (a `@contextmanager` generator's
  `finally` block runs if GC'd without an explicit `__exit__`, which would
  silently close the connection out from under `self.store`).
- `api.py`: new `GET /projects/{project_id}/documents` -> `list[Document]`,
  returning `[]` when `runtime.store is None` (deep research never enabled)
  rather than erroring.
- `pyproject.toml`: added `gpt-researcher>=0.15,<0.16` (pinned below `0.16`,
  which requires Python `>=3.12`, incompatible with this repo's
  `>=3.11,<3.14`) and `langchain-openai>=1.0`. `uv add` for both resolved
  cleanly on the dev machine -- a bare `pip download` attempt during design
  hit a Rust/`cryptography` build failure for one of gpt-researcher's
  transitive dependencies on Windows, but `uv`'s wheel resolution avoided it
  entirely; no workaround was needed. No new dependency for sqlite-vec --
  already transitive via `langgraph-checkpoint-sqlite`.
- `src/mythinking/config.py`: new `Settings` fields --
  `embedding_model`/`embedding_dimensions`, `context_retrieval_threshold`/
  `context_retrieval_top_k`, `enable_deep_research` (default `False`, same
  off-by-default convention as `enable_profile_extraction`),
  `research_retriever` (`"duckduckgo"` default -- free, keyless, fits a
  local-first personal tool; `"tavily"` opt-in), `tavily_api_key` +
  `has_tavily_key`/`require_tavily_key()` mirroring the existing
  `has_api_key`/`require_api_key()` pair. New `store_database_path` property
  (`data/store.sqlite`, a separate file from `state.sqlite`, mirroring why
  `checkpoints.sqlite` is already separate -- `SqliteStore` wants one
  long-lived connection, a different lifecycle from `StateRepository`'s
  per-call connections).
- `README.md`: documented `MYTHINKING_ENABLE_DEEP_RESEARCH` and the related
  settings, following the same prose-not-`.env.example` convention already
  used for `MYTHINKING_ENABLE_PROFILE_EXTRACTION` (neither flag is listed in
  `.env.example`); updated the foundation-layout file list.
- Also fixed, same session: a pre-existing intermittent flake in
  `tests/test_persistence.py` unrelated to M8 (surfaced repeatedly while
  running the full suite during M8 verification) -- `list_project_ids`/
  `list_recent`/`latest_project_id` ordered only by `updated_at DESC`, which
  ties when two saves land within the same real-world timestamp resolution
  window, leaving SQLite's tie-break order unspecified. Fixed by adding
  `rowid DESC` as a secondary, deterministic sort key (SQLite's implicit,
  monotonically increasing insert-order column) to all three queries in
  `src/mythinking/persistence.py`. Verified via 15 consecutive isolated runs
  plus 3 full-suite runs with no recurrence.
- Tests added (13 new files, several existing files extended):
  `tests/test_documents.py`, `tests/test_retrieval.py`,
  `tests/test_context.py`, `tests/test_deep_research.py`,
  `tests/test_researcher_agent.py`, `tests/test_frame_analyst.py`,
  `tests/test_evidence_analyst.py`, `tests/test_explorer.py`,
  `tests/test_synthesizer.py`, `tests/test_planner.py`,
  `tests/test_intent_classifier.py` (all new -- no dedicated per-agent test
  files existed before this milestone; each follows the existing
  `FakeModel`/`FakeStructuredModel` double and asserts the rendered prompt
  contains the new scoped placeholders and never a raw `"schema_version"`
  JSON dump); extended `tests/test_llm.py` (`create_embeddings_model`),
  `tests/test_config.py` (new settings), `tests/test_exploration.py`
  (`format_all_branch_names`), `tests/test_prompts.py` (`lead_partner` v8),
  `tests/test_graph.py` (indexing wiring for both node types, updated
  `FakeIntentClassifier` signature), `tests/test_runtime.py` (updated
  `StubIntentClassifier` signature), `tests/test_api.py` (documents
  endpoint).
- Commands run:
  - `uv run ruff format .`
  - `uv run ruff check .` (clean on every file touched this session; one
    pre-existing `cli.py` `SIM105` finding predates this session and is
    unrelated)
  - `uv run pytest` -- full suite green, multiple repeated runs including
    the persistence-ordering stress test
  - `uv add "gpt-researcher>=0.15,<0.16"`, `uv add "langchain-openai>=1.0"`
  - Manual smoke test of the `SqliteStore` retrieval wrapper (embed → index →
    similarity search round-trip) before building the rest of the stack on
    top of it, and of `GPTResearcher`'s actual constructor/method signatures
    against the installed `0.15.1` wheel

## Addendum: deep research gated by an explicit deterministic phrase

**Superseded by `M9` (see
`docs/handoffs/2026-08-26-m9-agentic-tool-calling.md`).** The mechanism
described below -- a hand-rolled Python keyword gate deciding whether the
gpt-researcher pass could run -- was replaced by the idiomatic LangChain
pattern: tools with clear docstrings, bound unconditionally, with the model's
own judgment deciding when to call them. `research.detect_deep_research_request`
and `ResearchIntent.deep` no longer exist. Left in place below as a record of
what was tried and why it changed, not as a description of current behavior.

Follow-up within the same session, prompted by explicit user feedback: "trigger
deep research when only asked explicitly." The original M8 design already
gated the whole `Researcher` subsystem behind `enable_deep_research`, and only
routed to it on `TurnIntent.RESEARCH` (the Intent Classifier's semantic
judgment) -- but once routed there, *every* research-intent turn ran a full
gpt-researcher web-search pass, including mild requests like "can you look
into whether that's true?" that don't necessarily warrant a costly live
search.

- `src/mythinking/state.py`: `ResearchIntent` gained `deep: bool = False` --
  a separate, deterministic sub-signal from `trigger`.
- `src/mythinking/research.py`: new `detect_deep_research_request(user_message)`
  -- deterministic substring matching against a trigger-phrase tuple
  (`"deep research"`, `"deep dive"`, `"go deep on"`, `"search the web"`, etc.),
  mirroring `branching.BranchSwitcher`'s existing deterministic trigger-phrase
  pattern rather than adding a second LLM classification. Deliberately not an
  LLM judgment call: the live web-search path has a real cost, so it should
  fire only on an unambiguous, literal signal, not the same semantic
  "research intent" judgment that already routes here for much milder asks.
- `src/mythinking/graph.py`: `_classify_intent_node` sets
  `ResearchIntent.deep` via the detector when routing to research;
  `_research_node` passes `deep=intent.deep` into `Researcher.analyze(...)`.
- `src/mythinking/agents/researcher.py`: `analyze(...)` gained a
  keyword-only `deep: bool = False` parameter. `deep_research_runner.run(...)`
  (the actual network call) and `_store_and_index(...)` now only execute when
  `deep=True`. Regardless of `deep`, the agent still calls
  `context_retriever.select_document_chunks(...)` -- so a plain follow-up
  question can freely reuse whatever a *prior* deep pass already indexed for
  the same project, at no new cost, rather than needing a fresh deep request
  every time.
- `prompts/researcher.v3.yaml` (new): added `{deep_research_performed}`
  ("true"/"false") so the model is told plainly whether a fresh web search
  ran this turn and never implies one happened when it didn't; when false and
  nothing relevant was already indexed, it's instructed to say resolving the
  question would need an explicit deep-research request rather than
  guessing.
- Tests: `tests/test_research.py` (`detect_deep_research_request` matches/
  non-matches), `tests/test_graph.py` (new
  `test_build_thinking_graph_marks_research_intent_deep_only_on_explicit_phrase`,
  extended the existing research-routing test to assert `deep is False` on a
  plain request; `FakeResearcher.analyze` gained the `deep` kwarg),
  `tests/test_runtime.py` (`StubResearcher.analyze` gained the `deep` kwarg),
  `tests/test_researcher_agent.py` (new: shallow requests never call the deep
  research runner; a prior deep pass's indexed content is reused for free on
  a later shallow turn).
- `README.md` updated to describe the two-tier behavior and the trigger
  phrase mechanism.
- Full suite green; `ruff check`/`format --check` clean on every file
  touched.

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- **`SqliteStore` (LangGraph's own) is the storage/retrieval engine, not a
  hand-rolled `sqlite-vec` table.** This was a mid-design pivot after
  checking what was already installed rather than assuming a custom build
  was needed -- see Completed. `retrieval.py` is a thin wrapper, not a second
  storage layer.
- **Document/chunk storage lives in a separate file, `data/store.sqlite`**,
  not merged into `state.sqlite` or bolted onto the checkpoint file --
  `SqliteStore` wants one long-lived, autocommit connection with its own
  internal lock, a different connection lifecycle from `StateRepository`'s
  per-call WAL connections. This mirrors the existing precedent of
  `checkpoints.sqlite` already being its own file for an analogous reason.
- **The store is constructed eagerly at `ThinkingRuntime.__init__`, once,
  gated by `enable_deep_research`** (not opened per-turn like the
  checkpointer). Rejected the "open per-call like the checkpointer" pattern:
  `Researcher`'s constructor needs a concrete `store` at construction time,
  and per-call reopening would mean either restructuring `Researcher` to
  take the store per-call or rebuilding it every turn -- more complexity for
  no correctness benefit, since a long-lived autocommit SQLite connection is
  not itself unsafe.
- **`create_embeddings_model`/the store are *not* constructed unconditionally**,
  even though local-file construction alone makes no network call. Every
  existing agent dependency (`create_chat_model`) is only constructed when
  no override was injected, and every test in `test_runtime.py` injects
  explicit doubles for every agent -- so `create_chat_model` (which requires
  an API key) was never actually exercised by the existing suite.
  Unconditionally constructing the embeddings client would have been the
  first thing in `__init__` to require a real key regardless of overrides,
  breaking that suite. Gating it behind `enable_deep_research` (same
  convention as every other optional agent) avoids this.
- **gpt-researcher's `write_report()` is unused.** Only
  `conduct_research()` + `get_research_sources()` feed the typed extraction
  step; the markdown report is a cost with no consumer in this design.
- **The context-scoping refactor's threshold/retrieval mechanism
  (`ContextRetriever`) is wired into `Researcher` only** (for
  `retrieved_context` and `existing_evidence_ledger`), not into
  `evidence_analyst`/`supervisor`'s own evidence-ledger rendering -- those
  keep the plain, always-full `format_evidence_ledger` regardless of list
  size. This is a real scope-narrowing worth flagging explicitly: the
  milestone's stated problem (unbounded evidence/research-task/decision
  growth) is only mitigated where `ContextRetriever` is actually called, not
  everywhere those fields are rendered. See Open issues.
- **`drift_judge.v1`'s raw `project_state` dump is an acknowledged 8th
  instance of the problem, deliberately left untouched** -- it wasn't one of
  the seven specialist agents named in scope, and touching it wasn't
  approved as part of this milestone's plan.
- `.env.example` was **not** updated with the new settings, matching the
  existing precedent that `MYTHINKING_ENABLE_PROFILE_EXTRACTION` also isn't
  listed there -- optional feature flags are documented in README prose
  instead.

## Open issues

- **The threshold-based retrieval mechanism doesn't yet cover
  `evidence_analyst`'s or `supervisor`'s own evidence/research-task/decision
  rendering** -- only `Researcher`'s two calls use `ContextRetriever`. As a
  project's evidence ledger grows past `context_retrieval_threshold`, the
  Evidence Analyst and the Supervisor will still receive the full list via
  `format_evidence_ledger`/`format_open_research_tasks`, which is exactly
  the unbounded-growth problem this milestone set out to fix for those two
  call sites specifically. Wiring `ContextRetriever` into
  `evidence_analyst.py` and `supervisor.py` (swapping their direct
  `format_evidence_ledger(...)` calls for
  `context_retriever.select_evidence(...)`) is the natural, scoped follow-up.
- `drift_judge.v1.yaml` (`drift.py:194`) still does the same raw
  `project_state.model_dump_json()` dump as the seven agents fixed here --
  a real, known 8th instance, intentionally out of scope for this milestone.
- `ContextRetriever.select_research_tasks`/`select_decisions` are built,
  tested, and unused by any live call site today (mirroring
  `format_decisions`'s inert-until-populated status) -- they exist for
  whichever future call site needs threshold-based retrieval over those
  fields.
- `sqlite-vec`'s native partition/metadata pre-filtering syntax (querying
  vectors with a `WHERE project_id = ?` scoped directly into the ANN search
  rather than overfetch-then-filter) was not investigated -- `SqliteStore`'s
  own implementation already handles per-namespace scoping correctly
  (verified by reading its source), so this wasn't a gap in practice, just
  an unexplored optimization axis if per-project data volume ever grows
  into the thousands of rows.
- No frontend surface for stored documents -- `GET /projects/{project_id}/documents`
  exists, but `frontend/` has no panel consuming it (deliberately out of
  scope; `EvidenceTimeline.tsx`-style work is separate follow-up).
- `asyncio.run()` inside `Researcher.analyze` (via `DeepResearchRunner.run`)
  is correct only as long as `api.py`'s routes and the graph invocation
  chain stay fully synchronous -- documented in code, not just here, since
  it would silently break if either became `async`.

## Next best task

- Close the evidence/research-task/decision threshold gap noted above:
  wire `ContextRetriever` into `evidence_analyst.py` and `supervisor.py` so
  the unbounded-growth fix actually covers every call site that renders
  those fields, not just the Researcher's.
- Alternatively: apply the same raw-dump fix to `drift_judge.v1.yaml` /
  `drift.py`, closing the 8th instance noted above -- small, isolated,
  same pattern as the seven agents already done.
- A frontend documents panel over the new `GET /projects/{project_id}/documents`
  endpoint, once there's a concrete UI need for it.
