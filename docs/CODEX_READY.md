# Codex Ready

This repository is prepared for multi-session Codex implementation.

## What this means

- The architecture contract is fixed enough to start coding.
- The implementation plan is broken into sequential milestones.
- Each milestone is designed for supervisor-led, subagent-driven execution.
- Session handoff expectations are explicit, so work can resume without
  rebuilding context from scratch.

## Source of truth

- Product and engineering guardrails: [AGENTS.md](D:/MyThinking/AGENTS.md)
- Human overview and setup: [README.md](D:/MyThinking/README.md)
- Implementation roadmap: [IMPLEMENTATION_PLAN.md](D:/MyThinking/docs/IMPLEMENTATION_PLAN.md)
- Subagent workflow: [SUBAGENT_DEVELOPMENT.md](D:/MyThinking/docs/SUBAGENT_DEVELOPMENT.md)
- Session handoff template: [SESSION_HANDOFF_TEMPLATE.md](D:/MyThinking/docs/SESSION_HANDOFF_TEMPLATE.md)

## Next session startup

1. Read [AGENTS.md](D:/MyThinking/AGENTS.md) and [docs/IMPLEMENTATION_PLAN.md](D:/MyThinking/docs/IMPLEMENTATION_PLAN.md).
2. Pick exactly one milestone or one tightly scoped slice of a milestone.
3. Use subagents for parallelizable work only after interfaces and acceptance
   criteria are fixed.
4. Update docs if an implementation decision changes the plan or interfaces.
5. Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest`.

## Immediate next milestone

Milestone `M1`: implement the first runnable LangGraph workflow:

`capture -> frame -> choose_mode -> respond -> persist`

This milestone should produce a local `mythinking chat` command with:

- a supervisor graph,
- a Frame Analyst subagent,
- persisted thread/project state,
- deterministic mode selection rules,
- offline tests for state transitions and prompt loading.

## Boundaries

- Do not add browser research, voice, or UI work before the graph loop exists.
- Do not add free-form agent-to-agent chat.
- Do not introduce extra frameworks when LangChain, LangGraph, stdlib SQLite,
  and Pydantic cover the use case.
