# Contributing to MyThinking

Contributions are welcome — issues, discussion, and PRs alike.

## Before you start

Read [`AGENTS.md`](AGENTS.md) — the product contract and the architecture rules
the codebase holds itself to. The two that matter most:

- **Do not reintroduce a multi-agent graph or an intent classifier.** MyThinking
  is one conversational agent whose tool selection is the router.
- **Keep board-mutation correctness in deterministic tool preconditions**, not in
  prompt text.

[`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) is the milestone
roadmap and the record of design decisions.

## Development setup

```bash
uv sync
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
uv run mythinking init
```

Setup and the test suite make no API request; an OpenRouter key is only needed to
actually chat with the agent.

## Checks to run before opening a PR

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

For frontend changes, also run in `frontend/`:

```bash
npm run typecheck
npm run test
```

## Expectations

- Every behavior change ships with tests.
- Prompts are versioned YAML in `prompts/`. Every behavioral instruction needs
  either an evidence entry or an explicit `product_hypothesis` label, plus an
  evaluation case in `evals/`.
- Never commit API keys, conversation data, databases, or model traces.
