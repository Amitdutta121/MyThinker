# MyThinking Engineering Guide

## Product contract

MyThinking is a personal, stateful thinking partner. One supervisor owns every
user-facing response and invokes specialists as bounded tools. Do not implement
free-form agent-to-agent conversation.

The system must help the user clarify an idea, expose assumptions and gaps,
explore alternatives, research evidence, detect drift, preserve useful branches,
and finish with a decision or next experiment.

## Architecture rules

- Use Python 3.11+, LangChain, and LangGraph.
- Access models only through `mythinking.llm.create_chat_model`.
- Use OpenRouter through `langchain-openrouter`; never add provider-specific
  calls inside agents.
- Represent application and graph state with Pydantic models.
- Keep deterministic state transitions separate from model-driven judgments.
- Persist project snapshots and LangGraph checkpoints in local SQLite files.
- Keep prompts in `prompts/` as versioned YAML specifications.
- Every behavioral prompt instruction needs an evidence entry or an explicit
  `product_hypothesis` label and an evaluation case.
- Never commit API keys, conversation data, databases, or model traces.

## Codex execution rules

- Treat [docs/IMPLEMENTATION_PLAN.md](D:/MyThinking/docs/IMPLEMENTATION_PLAN.md)
  as the milestone source of truth.
- Implement with a lead-agent plus subagent pattern, not free-form parallel
  coding.
- Freeze interfaces before delegating work to subagents.
- Prefer one active milestone or milestone slice per session.
- Update docs when interfaces, milestones, or prompt contracts change.
- Leave a clear handoff using
  [docs/SESSION_HANDOFF_TEMPLATE.md](D:/MyThinking/docs/SESSION_HANDOFF_TEMPLATE.md)
  when a session ends.

## Quality rules

- Add or update tests with every behavior change.
- Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest`.
- Model-dependent behavior must have offline fixtures and must not require a
  live API key during the normal test suite.
- Keep modules narrow. Prefer library abstractions over custom framework code,
  but do not add a dependency for behavior covered clearly by the standard
  library.
