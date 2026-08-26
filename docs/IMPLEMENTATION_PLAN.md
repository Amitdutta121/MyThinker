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

### M7: UI layer

Goal: add a minimal interface after the core workflow is stable.

Deliverables:

- Streamlit or similar local UI,
- streaming output,
- branch and evidence panels,
- session selector.

Acceptance criteria:

- The UI is thin over the existing runtime.
- Core logic remains testable without the UI.

## Rules for milestone execution

- Only one milestone should be in active implementation at a time.
- Finish interfaces and tests before adding additional specialists.
- When a milestone expands, split it into `M1a`, `M1b`, and so on rather than
  silently increasing scope.
- Every new prompt or behavior change must add or update an eval case.
