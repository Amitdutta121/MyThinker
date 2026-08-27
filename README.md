# MyThinking

MyThinking is a personal, stateful AI thinking partner. Since M10 it is **one
conversational agent** (`langchain.agents.create_agent`) whose tool selection is
the router. It answers ordinary questions directly and updates a persistent
idea / decision / plan board only through tools that each enforce a deterministic
precondition (a North Star must exist before exploration; convergence writes a
proposal, never a commitment; a commit copies the exact proposal only on explicit
user authorization; planning requires a committed direction; source material is
never auto-promoted to evidence). Framing, exploring, converging, and planning
are structured-output engines invoked inside those tools, not separate agents.

This repository contains OpenRouter model configuration, typed project state,
SQLite persistence (board, chat checkpoints, and a document store), versioned
prompt specifications, the single-agent runtime, and offline tests. It
intentionally does not make an API request during setup or testing. The
architecture was validated in
`notebooks/thinker_final_architecture_validation (1).ipynb` before the pivot.

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
uv run mythinking profile
```

Run the HTTP API (a thin, non-streaming adapter over the same runtime):

```powershell
uv run mythinking serve
```

```text
GET    /health                                   liveness check
POST   /turns                                    {"message": "...", "project_id": "..."} -> AssistantTurn
POST   /turns/stream                             same request body -> text/event-stream of TurnStreamEvent frames
GET    /projects?limit=20                        recent project summaries, newest first
GET    /projects/{project_id}                    full ProjectState

# Direct edits (no agent turn). Each returns the updated ProjectState;
# KeyError -> 404, ValueError -> 400. Logic lives in runtime.py / board.py.
PATCH  /projects/{id}/north-star                 {"title": "..."}
POST   /projects/{id}/decisions                  {"question?": "...", "choice": "...", "rationale?": "...", "reversible?": true}
PATCH  /projects/{id}/decisions/{decision_id}    partial of the same fields
DELETE /projects/{id}/decisions/{decision_id}
POST   /projects/{id}/proposal/approve           commit the pending proposal verbatim
DELETE /projects/{id}/proposal                   dismiss the pending proposal
POST   /projects/{id}/next-actions               {"description": "...", "time_box_minutes?": 30, ...}  (origin="user")
PATCH  /projects/{id}/next-actions/{action_id}   partial; also toggles completed
DELETE /projects/{id}/next-actions/{action_id}
```

User-added plan steps (`origin="user"`) survive re-planning and are not marked
stale by a direction change; the agent sequences its own steps around them.

`POST /turns/stream` streams one Server-Sent Event per tool the agent runs
(`{"type": "node", "node": "<tool name>"}`), followed by a final
`{"type": "turn", "turn": <AssistantTurn>}` event. A failure that happens after
streaming has started (the HTTP status is already committed) is delivered as a
terminal `{"type": "error", "detail": "..."}` event instead of a dropped
connection.

CORS is enabled for the local Next.js dev server (`http://localhost:3000` and
`http://127.0.0.1:3000`, plus `:3001` for when `3000` is already taken and
Next falls back to it).

The default model is OpenRouter's `~openai/gpt-latest` alias. Set
`OPENROUTER_MODEL` to any supported `provider/model` slug when you want a fixed
model. Model availability, capabilities, and pricing should be checked in the
[OpenRouter model catalog](https://openrouter.ai/models).

Cross-project user-profile extraction (role, expertise, working style -- never
sensitive personal details) is off by default. Set
`MYTHINKING_ENABLE_PROFILE_EXTRACTION=true` to turn it on, then inspect what
was captured with `uv run mythinking profile`.

Research is agentic and built into the one agent: it always has `web_search`
and `fetch_url`, and decides for itself, from each tool's description, whether
it needs them. Fetched web
and document content is source material -- it becomes project evidence only via
an explicit `save_evidence` call that passes a source-support and
project-relevance check. The web-search retriever
defaults to the free, keyless DuckDuckGo (`ddgs`); set
`MYTHINKING_RESEARCH_RETRIEVER=tavily` and `TAVILY_API_KEY` to use Tavily
instead. Fetched content is stored in `data/store.sqlite` (a LangGraph
`SqliteStore`, separate from `state.sqlite`) and is listable via
`GET /projects/{project_id}/documents`. `search_documents` returns each passage
under a citation tag -- `[[file.pdf p.3]]` for an ingested PDF (chunked page by
page), `[[Title]]` for a web source -- and the system prompt requires those tags
to be copied verbatim into any document-grounded answer. Ordinary chat replies get the same
kind of self-directed lookup, scoped to the project's own saved
evidence/research-tasks/branches/next-actions (no internet access) --
the assistant calls a tool like `get_evidence_ledger` only when a turn's
question actually needs it, instead of always receiving a fixed context
bundle. Embeddings for retrieval (of fetched research content and, once a
project's evidence or research tasks grow past
`MYTHINKING_CONTEXT_RETRIEVAL_THRESHOLD` items, of project state itself)
are produced through the same OpenRouter key, via `MYTHINKING_EMBEDDING_MODEL`
(default `openai/text-embedding-3-small`).

## Frontend

The immersive workspace UI (M7c) lives in `frontend/`, a Next.js/TypeScript
app that talks to the API above over HTTP only:

```powershell
cd frontend
npm install
npm run dev
```

By default it targets `http://127.0.0.1:8000`; set `NEXT_PUBLIC_API_BASE_URL`
(see `.env.local.example`) to point elsewhere. Run `uv run mythinking serve`
in another terminal first so the app has something to talk to. See
`frontend/README` structure notes in
[docs/handoffs/2026-08-26-m7c-immersive-workspace.md](D:/MyThinking/docs/handoffs/2026-08-26-m7c-immersive-workspace.md)
for the frontend layout and commands (`npm run typecheck`, `npm run test`,
`npm run build`, `npm run generate:types`).

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
  documents.py    Full-text research documents and chunks, page-tracked for PDFs (outside ProjectState)
  retrieval.py    Typed wrapper around LangGraph's SqliteStore for semantic search
  context.py      Scoped per-agent context formatting and threshold-based retrieval
  gates.py        North Star / decision / evidence structured-output gates (M10)
  board.py        MutableStateHolder, derive_mode, plan staleness, frame merge (M10)
  tools.py        The agent's tools: state-changing thinking tools with
                  deterministic preconditions, read-only lookups, document tools,
                  and the web tools (web_search, fetch_url)
  prompts.py      Versioned prompt registry
  agent.py        The single create_agent loop + context-injection middleware (M10)
  runtime.py      Turn orchestration and persistence
  summary.py      Deterministic, offline session summary rendering
  api.py          HTTP API over the runtime (M7a non-streaming + M7b SSE streaming)
  agents/         Specialist structured-output engines invoked inside tools
  cli.py          Local setup, smoke, chat, list, show, and serve commands
prompts/           Research-linked prompt specifications
evals/             Offline behavioral evaluation cases
tests/             Deterministic unit tests
frontend/          Next.js/TypeScript immersive workspace UI (M7c), HTTP-only
```

OpenRouter's current LangChain integration uses `ChatOpenRouter` from the
dedicated `langchain-openrouter` package. See the
[OpenRouter guide](https://openrouter.ai/docs/guides/community/langchain) and
[LangChain integration reference](https://docs.langchain.com/oss/python/integrations/chat/openrouter).

## Current runnable flow

Each turn:

```text
load board -> run the Thinker agent (tools enforce preconditions,
mutate the board in place) -> derive display mode -> persist -> AssistantTurn
```

The chat thread persists in `data/checkpoints.sqlite` (per `project_id`), the
board in `data/state.sqlite`, and fetched/ingested documents in
`data/store.sqlite`. `mythinking serve` exposes non-streaming `POST /turns`
(M7a) and SSE `POST /turns/stream` (M7b) over the same runtime; `frontend/`
(M7c) is a Next.js workspace UI over that API.

## Codex session rule

When continuing implementation in a new Codex session, start from
[docs/CODEX_READY.md](D:/MyThinking/docs/CODEX_READY.md) and execute exactly one
milestone or one milestone slice at a time.
