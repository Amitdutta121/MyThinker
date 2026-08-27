# Implementation Plan

This plan is the execution contract for future Codex sessions. Each milestone is
small enough to be shipped and tested independently.

## Architecture decisions and citations

- Use a supervisor pattern with bounded specialists rather than equal peers.
  LangChain's subagent guidance describes the supervisor as the agent that owns
  conversation context and decides when to call specialists.
  Source: [LangChain subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents)
- Build specialists as subgraphs or tool-like units with explicit interfaces.
  LangGraph's subgraph documentation recommends subgraphs for multi-agent
  systems and distributed development with stable input/output schemas.
  Source: [LangGraph subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- Implement the product as a graph workflow with routing rather than ad hoc
  loops. LangGraph's workflow guide distinguishes deterministic workflows from
  dynamic agents and documents orchestrator-worker patterns.
  Source: [LangGraph workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- Persist short-term thread state with checkpointers and application state in a
  store. LangGraph persistence separates thread-scoped checkpoints from
  application-defined longer-lived memory.
  Source: [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- Keep model access provider-neutral through `ChatOpenRouter`, which supports
  tool calling and structured output in the official LangChain integration.
  Sources: [LangChain ChatOpenRouter](https://docs.langchain.com/oss/python/integrations/chat/openrouter),
  [OpenRouter LangChain guide](https://openrouter.ai/docs/guides/community/langchain)
- Keep prompts explicit, structured, and testable. Anthropic's prompt guidance
  emphasizes clear instructions, grounded context, and examples over vague
  high-level prompts.
  Sources: [Anthropic prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices),
  [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## Milestones

### M1: Runnable core loop

Goal: create the first end-to-end graph the user can run locally.

Deliverables:

- `src/mythinking/graph.py`
- `src/mythinking/agents/supervisor.py`
- `src/mythinking/agents/frame_analyst.py`
- `src/mythinking/runtime.py`
- `mythinking chat` CLI command
- tests for graph transitions and persistence

Scope:

- one user-facing supervisor,
- one Frame Analyst specialist,
- deterministic `choose_mode` logic,
- state load/save,
- structured assistant response object,
- no external research tools,
- no UI.

Acceptance criteria:

- A user can start or resume a session from the CLI.
- The graph persists state and checkpoints locally.
- The supervisor can call the Frame Analyst and return one coherent response.
- Tests cover at least one capture flow and one clarify flow.

Suggested subagent split:

- Subagent A: graph state contracts and runtime wiring
- Subagent B: supervisor and frame analyst prompt execution
- Subagent C: tests for transitions, persistence, and CLI behavior

### M2: Drift control and branch management

Goal: keep the user anchored while preserving side ideas.

Deliverables:

- drift detector service,
- branch/parking lot service,
- state updates for tangent capture,
- tests for drift detection and branch preservation.

Scope:

- deterministic drift heuristics first,
- model judgment only when deterministic signals are insufficient,
- no research web calls yet.

Acceptance criteria:

- The system can identify likely drift and explicitly offer return-to-goal or
  park-the-idea actions.
- Tangents become branches or parked ideas instead of disappearing.

Suggested slice order:

- M2a: deterministic drift heuristics plus tangent preservation into branches or
  parked ideas
- M2b: model fallback when heuristics are inconclusive plus explicit
  user-directed branch switching

Suggested subagent split:

- Subagent A: deterministic drift heuristics
- Subagent B: branch state transitions
- Subagent C: response phrasing and tests

### M3: Evidence and research ledger

Goal: separate facts, inferences, and hypotheses with citations.

Deliverables:

- evidence ledger service,
- research task schema,
- citation-aware response formatter,
- offline fixtures for evidence extraction and answer formatting.

Scope:

- evidence objects stored in state,
- support user-provided sources first,
- browser-backed research can be added later behind explicit tools.

Acceptance criteria:

- Responses can distinguish supported claims from open hypotheses.
- Evidence items are written into project state with source metadata.

Suggested subagent split:

- Subagent A: evidence schema and persistence
- Subagent B: response formatter and citation rendering
- Subagent C: eval cases and tests

### M4: Explore and converge specialists

Goal: support divergent thinking without losing the decision path.

Deliverables:

- Explorer specialist,
- Synthesizer specialist,
- mode routing updates,
- tests for alternative generation and convergence summaries.

Acceptance criteria:

- The system can produce multiple alternatives and then synthesize tradeoffs.
- Branches can be merged into a decision-ready summary.

Suggested subagent split:

- Subagent A: explorer specialist
- Subagent B: synthesizer specialist
- Subagent C: routing logic and tests

### M5: Researcher specialist and explicit research mode

Goal: support focused, scoped research tasks.

Deliverables:

- Researcher specialist,
- research question schema,
- evidence import pipeline,
- tests for scoped research requests.

Acceptance criteria:

- Research mode starts only when the user asks for it or the supervisor makes a
  traceable recommendation.
- Research outputs update the evidence ledger rather than free-form notes.

### M6: Personal workflow features

Goal: make the system practical for daily solo use.

Deliverables:

- recent-session resume flow,
- next-action planning,
- session summaries,
- optional user profile extraction,
- quality-of-life CLI improvements.

Acceptance criteria:

- The user can stop and resume work without losing the thread.
- Each session can finish with a decision, branch, or next experiment.

Suggested slice order:

- M6a: recent-session resume flow (`list`/`show` CLI commands, `chat --last`)
  plus deterministic, offline session summaries
- M6b: next-action planning (a Planner specialist that proposes structured
  `NextAction` entries)
- M6c: optional user profile extraction, off by default

### M7: Immersive UI layer

Goal: replace the thin, form-style interface originally planned here with a rich
web frontend that makes the thinking state (north star, branches, evidence,
decisions, next actions) feel alive and navigable, not just a list of records.

Deliverables:

- an HTTP/WebSocket API layer (FastAPI or similar) over `ThinkingRuntime` that
  exposes turn submission, streaming assistant output, and full `ProjectState`
  reads,
- streaming support in the runtime/graph (e.g. `graph.stream`) so the API can
  push incremental output instead of only a completed `AssistantTurn`,
- a React/Next.js frontend with:
  - a streaming chat surface for the active turn,
  - a visual workspace panel that renders branches, evidence, decisions, and
    next-actions as navigable elements (e.g. a branch graph, an evidence
    timeline, a decision history) rather than static lists,
  - animated transitions when `current_mode` changes (capture/drift/explore/
    converge/research/plan) so the UI reflects what the supervisor is doing,
  - a session selector built on M6a's list/show data,
- API contract tests (e.g. FastAPI `TestClient`) and offline frontend fixtures
  so CI never depends on a live LLM call.

Scope:

- core runtime/graph/state logic stays UI-agnostic; the API layer only adapts
  `ThinkingRuntime` and holds no business logic of its own,
- the frontend talks to the API over HTTP/WebSocket only; it never imports
  Python or duplicates supervisor/specialist logic,
- visual richness (animation, spatial layout) is additive polish and must
  degrade to functional plain views without breaking data flow.

Acceptance criteria:

- The frontend is thin over the API, and the API is thin over
  `ThinkingRuntime` — no duplicated business logic in either layer.
- Assistant responses stream to the browser instead of waiting for the full
  turn to complete.
- Branches, evidence, decisions, and next-actions are visually explorable
  rather than printed as raw lists or JSON.
- Core logic remains testable without the API or the frontend running.

Suggested slice order:

- M7a: FastAPI backend exposing `run_turn` (non-streaming first) and project
  state reads, with contract tests
- M7b: end-to-end streaming (graph streaming through to a WebSocket/SSE feed
  in the browser)
- M7c: the Next.js immersive workspace (branch/evidence/decision panels,
  animated mode transitions, session selector)

### M8: Retrieval, document storage, and context management

Goal: move past the prototype's two accumulated liabilities -- research mode
had no real external search, and every specialist agent (plus the supervisor,
redundantly) sent the *entire* `ProjectState` as raw JSON into every LLM call,
an unbounded-growth problem as evidence/decisions/research tasks accumulate --
without inventing new storage infrastructure where an already-installed one
exists.

Deliverables:

- a `Document`/`DocumentChunk` store for full research-source text, kept
  outside the small `ProjectState` JSON blob (`documents.py`),
- one reusable retrieval mechanism backed by LangGraph's own
  `langgraph.store.sqlite.SqliteStore` (already transitively installed via
  `langgraph-checkpoint-sqlite`, with built-in sqlite-vec-backed vector
  search) rather than a hand-rolled vector index (`retrieval.py`),
- gpt-researcher wired into the `Researcher` specialist for real multi-source
  web research, feature-flagged off by default (`deep_research.py`,
  `Settings.enable_deep_research`), with the `ResearcherAnalysis` output
  contract unchanged so `ResearchImporter.merge` needed no changes,
- every specialist agent's context reduced to only the state its own prompt
  actually references, with a threshold-based full-list-vs-retrieval split
  for fields that can grow unboundedly (`context.py`, `ContextRetriever`),
- a minimal `GET /projects/{project_id}/documents` read endpoint so stored
  documents aren't stranded from the API.

Scope:

- storage/retrieval is additive infrastructure; it must not change the
  merge/format contracts (`EvidenceLedger.merge`, `ResearchImporter.merge`,
  `format_evidence_ledger`, etc.) that the rest of the graph already depends
  on and tests against,
- gpt-researcher's own `write_report()` is deliberately unused -- only
  `conduct_research()` + `get_research_sources()` feed the existing typed
  extraction step,
- context-scoping change is per-agent and grounded in each prompt's actual
  placeholders, not a blanket "strip project_state everywhere" pass.

Acceptance criteria:

- No specialist agent (or the supervisor) passes a raw
  `project_state.model_dump_json()` dump into its prompt.
- With `MYTHINKING_ENABLE_DEEP_RESEARCH=false` (default), a full turn
  completes with no network research call.
- With it enabled, a research turn stores and indexes real fetched sources,
  and the resulting evidence lands in `ProjectState.evidence` exactly as the
  pre-M8 single-LLM-pass researcher would have shaped it.
- Every new component follows this repo's existing testing conventions
  (`FakeModel`/`FakeStructuredModel` doubles, real `tmp_path` SQLite, pure
  formatter tests) rather than introducing a new one.

### M9: Agentic tool-calling for research and chat replies

Goal: make the chat window feel agentic -- the assistant decides for itself,
mid-turn, whether it already has enough information or needs to look
something up, instead of following one fixed pipeline every time. Applies
to two places: the `Researcher` (real web research, self-directed) and the
`Supervisor` (self-directed lookup over the project's own saved notes, no
internet access).

This milestone deliberately reverses part of `M8`'s own follow-up work: `M8`
added a hand-rolled deterministic keyword gate
(`research.detect_deep_research_request`) deciding in Python whether the
costly gpt-researcher pass could run. `M9` replaces that with the actual
LangChain-idiomatic mechanism -- tools with clear docstrings, bound
unconditionally, with the model's own tool-selection judgment (guided by
those docstrings) deciding when to use them. See
`docs/handoffs/2026-08-26-m9-agentic-tool-calling.md` for the full record,
including why the reversal happened.

Deliverables:

- `tools.py`: `build_research_tools` (`web_search`, `fetch_url`, and --
  only when `Settings.enable_deep_research` is on -- `run_deep_research`,
  wrapping the still-present gpt-researcher integration) and
  `build_context_tools` (read-only lookups over a project's own saved
  evidence/research-tasks/branches/next-actions, no internet access),
- `Researcher`/`SupervisorAgent` rewritten around `langchain.agents.create_agent`
  with `response_format=<their existing typed schema>`, so the rest of the
  graph's merge/post-processing logic never changes,
- `ModelCallLimitMiddleware`/`ToolCallLimitMiddleware` as the cost/latency
  guardrail replacing the removed keyword gate,
- `researcher.v4.yaml`/`lead_partner.v9.yaml`: system prompts instructing
  the model on when each tool is (and isn't) appropriate.

Scope:

- the output contract of both agents (`ResearcherAnalysis`, `SupervisorReply`)
  and everything downstream of it is unchanged -- this milestone only
  changes how that typed output gets produced,
- graph-level routing (which turns even reach the Researcher/Supervisor)
  is unchanged -- only what happens once inside those specialists changes,
- no new commands or UI surface; the agentic behavior is invisible to the
  user beyond the assistant sometimes doing more before it answers.

Acceptance criteria:

- No Python code decides which research tool is appropriate for a given
  message -- that judgment is the model's, informed by each tool's
  docstring.
- `run_deep_research` is present in the Researcher's toolset only when
  `enable_deep_research` is on; `web_search`/`fetch_url` are always present
  whenever the Researcher runs at all.
- The Supervisor never has internet-access tools, only read-only lookups
  over the current project's own saved state.
- A `create_agent` loop that ends without producing the expected typed
  output degrades to a safe, honest fallback rather than crashing.

## Rules for milestone execution

- Only one milestone should be in active implementation at a time.
- Finish interfaces and tests before adding additional specialists.
- When a milestone expands, split it into `M1a`, `M1b`, and so on rather than
  silently increasing scope.
- Every new prompt or behavior change must add or update an eval case.
