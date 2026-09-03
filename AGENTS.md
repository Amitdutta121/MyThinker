# MyThinking Engineering Guide

## Product contract

MyThinking is a personal, stateful thinking partner. Since M10 it is **one
conversational agent** (`langchain.agents.create_agent`, see `agent.py`) whose
tool selection is the router. Specialists (framing, exploring, converging,
planning, evidence) are structured-output engines invoked *inside* tools, not
peers in a graph. Do not reintroduce a hand-wired workflow or an intent
classifier; do not implement free-form agent-to-agent conversation.

The system must help the user clarify an idea, expose assumptions and gaps,
explore alternatives, research evidence, keep the North Star in view, preserve
useful branches, and finish with a decision or next experiment.

## Architecture rules

- Use Python 3.11+ and LangChain (`create_agent` + middleware).
- Access models only through `mythinking.llm.create_chat_model`.
- Use OpenRouter through `langchain-openrouter`; never add provider-specific
  calls inside agents.
- Represent application state with Pydantic models.
- Correctness of board mutations lives in deterministic tool preconditions
  (`tools.build_thinking_tools`), which fail safe with a `BLOCKED:` string;
  keep those separate from model-driven judgment.
- Persist project snapshots and LangGraph checkpoints in local SQLite files.
- Keep prompts in `prompts/` as versioned YAML specifications.
- Every behavioral prompt instruction needs an evidence entry or an explicit
  `product_hypothesis` label and an evaluation case.
- Never commit API keys, conversation data, databases, or model traces.

## Codex execution rules

- Treat [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
  as the milestone source of truth.
- Implement with a lead-agent plus subagent pattern, not free-form parallel
  coding.
- Freeze interfaces before delegating work to subagents.
- Prefer one active milestone or milestone slice per session.
- Update docs when interfaces, milestones, or prompt contracts change.
- Leave a clear handoff using
  [docs/SESSION_HANDOFF_TEMPLATE.md](docs/SESSION_HANDOFF_TEMPLATE.md)
  when a session ends.

## Quality rules

- Add or update tests with every behavior change.
- Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest`.
- Model-dependent behavior must have offline fixtures and must not require a
  live API key during the normal test suite.
- Keep modules narrow. Prefer library abstractions over custom framework code,
  but do not add a dependency for behavior covered clearly by the standard
  library.
