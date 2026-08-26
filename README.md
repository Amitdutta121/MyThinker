# MyThinking

MyThinking is a personal, stateful AI thinking partner. The application will use
one user-facing supervisor with bounded specialist agents for framing, exploring,
researching, and synthesizing ideas.

This repository now contains the verified M1 core loop foundation plus the
first M2a drift-control slice: OpenRouter model configuration, typed project
and graph state, SQLite persistence, versioned prompt specifications, a
runnable LangGraph supervisor loop with deterministic tangent preservation, and
offline tests. It intentionally does not make an API request during setup or
testing.

The repo is also prepared for multi-session Codex implementation. The execution
roadmap and subagent workflow live in:

- [docs/CODEX_READY.md](D:/MyThinking/docs/CODEX_READY.md)
- [docs/IMPLEMENTATION_PLAN.md](D:/MyThinking/docs/IMPLEMENTATION_PLAN.md)
- [docs/SUBAGENT_DEVELOPMENT.md](D:/MyThinking/docs/SUBAGENT_DEVELOPMENT.md)

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An [OpenRouter API key](https://openrouter.ai/settings/keys)

## Setup

```powershell
uv sync
Copy-Item .env.example .env
```

Edit `.env` and set your key:

```dotenv
OPENROUTER_API_KEY=your-key-here
```

Do not paste the key into source files or commit `.env`.

Initialize local storage and inspect the configuration:

```powershell
uv run mythinking init
uv run mythinking status
```

After adding a funded or otherwise usable OpenRouter key, verify one live model
request:

```powershell
uv run mythinking smoke-model
uv run mythinking chat "I want help thinking through a product idea."
uv run mythinking chat --project-id <existing-project-id> "Here is more context."
uv run mythinking chat --last "Continue where I left off."
uv run mythinking list
uv run mythinking show <existing-project-id>
```

Run the HTTP API (a thin, non-streaming adapter over the same runtime):

```powershell
uv run mythinking serve
```

```text
GET  /health                 liveness check
POST /turns                  {"message": "...", "project_id": "..."} -> AssistantTurn
GET  /projects?limit=20      recent project summaries, newest first
GET  /projects/{project_id}  full ProjectState
```

The default model is OpenRouter's `~openai/gpt-latest` alias. Set
`OPENROUTER_MODEL` to any supported `provider/model` slug when you want a fixed
model. Model availability, capabilities, and pricing should be checked in the
[OpenRouter model catalog](https://openrouter.ai/models).

## Development

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest
```

Useful commands:

```powershell
uv run mythinking status
uv run mythinking init
uv run mythinking smoke-model
uv run mythinking chat "I want help clarifying this idea."
```

## Foundation layout

```text
src/mythinking/
  config.py       Environment and OpenRouter settings
  llm.py          The only model-construction boundary
  state.py        Typed thinking and project state
  persistence.py  Project snapshots and LangGraph checkpoints
  prompts.py      Versioned prompt registry
  graph.py        Runnable LangGraph workflow
  runtime.py      Turn orchestration and persistence
  summary.py      Deterministic, offline session summary rendering
  api.py          HTTP API over the runtime (M7a: non-streaming)
  agents/         Supervisor and specialist agents
  cli.py          Local setup, smoke, chat, list, show, and serve commands
prompts/           Research-linked prompt specifications
evals/             Offline behavioral evaluation cases
tests/             Deterministic unit tests
```

OpenRouter's current LangChain integration uses `ChatOpenRouter` from the
dedicated `langchain-openrouter` package. See the
[OpenRouter guide](https://openrouter.ai/docs/guides/community/langchain) and
[LangChain integration reference](https://docs.langchain.com/oss/python/integrations/chat/openrouter).

## Current runnable flow

The current CLI runs the first M1 workflow:

```text
capture -> frame -> choose_mode -> respond -> persist
```

The current verified runtime flow is:

```text
capture -> frame -> detect_drift -> choose_mode -> respond -> persist
```

The current slice includes the supervisor, Frame Analyst, and deterministic
drift preservation. The `mythinking serve` HTTP API (M7a) is now available as a
non-streaming adapter over the same runtime; streaming (M7b) and the immersive
React/Next.js frontend (M7c) are still later slices of M7.

## Codex session rule

When continuing implementation in a new Codex session, start from
[docs/CODEX_READY.md](D:/MyThinking/docs/CODEX_READY.md) and execute exactly one
milestone or one milestone slice at a time.
