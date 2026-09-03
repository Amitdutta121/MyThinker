# MyThinking

**A stateful AI thinking partner.** MyThinking helps you take a raw idea and
work it all the way to a decision or a next experiment — clarifying the goal,
surfacing assumptions and gaps, exploring alternatives, gathering evidence, and
keeping the through-line in view the whole time. It remembers every project
across sessions.

It is **one conversational agent**, not a pipeline of bots. The agent answers
ordinary questions directly and reaches for a tool only when the work calls for
one. Its **tool selection is the router** — there is no intent classifier and no
hand-wired workflow graph.

```
you ──▶ Thinker agent ──▶ tools (each with a hard precondition) ──▶ project board
                                                                        │
              persistent SQLite  ◀───────────────────────────────────────┘
```

---

## Why it's built this way

Most "agent" systems are a maze of sub-agents passing messages. MyThinking makes
the opposite bet: **one agent, a small set of sharp tools, and correctness pushed
into deterministic code** rather than left to the model's judgement.

Every tool that changes the project board checks a precondition first and fails
safe with a `BLOCKED: …` string if it isn't met:

| Rule | Enforced by |
| --- | --- |
| A **North Star** must exist before exploration begins | `explore_ideas`, `converge_ideas` |
| Convergence writes a **proposal**, never a commitment | `converge_ideas` |
| A commit copies the **exact proposal**, only on explicit user authorization | `commit_proposed_direction` |
| Planning requires a **committed direction** | `create_or_revise_plan` |
| Source material is **never auto-promoted** to evidence | `save_evidence` (source-support + relevance check) |
| User-added plan steps **survive re-planning** and direction changes | `create_or_revise_plan` |

Framing, exploring, converging, and planning are **structured-output engines**
invoked *inside* those tools — not separate agents in a conversation. The
architecture was validated end-to-end in the notebook under
[`notebooks/`](notebooks/) before the single-agent pivot.

Everything runs against local SQLite. Setup and the test suite make **no API
request**.

---

## Quickstart

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An [OpenRouter API key](https://openrouter.ai/settings/keys)

### Setup

```bash
uv sync
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
```

Edit `.env` and set your key (never commit `.env` or paste keys into source):

```dotenv
OPENROUTER_API_KEY=your-key-here
```

Initialize local storage and check the configuration:

```bash
uv run mythinking init
uv run mythinking status
```

### Talk to it

```bash
uv run mythinking smoke-model                       # one small live request
uv run mythinking chat "Help me think through a product idea."
uv run mythinking chat --last "Continue where I left off."
uv run mythinking chat --project-id <id> "Here is more context."
uv run mythinking list
uv run mythinking show <id>
uv run mythinking profile
```

The default model is OpenRouter's `~openai/gpt-latest` alias. Set
`OPENROUTER_MODEL` to any `provider/model` slug to pin a fixed model — check the
[OpenRouter catalog](https://openrouter.ai/models) for availability and pricing.

---

## The tools

**Thinking** (mutate the board, precondition-gated): `set_north_star` ·
`explore_ideas` · `converge_ideas` · `commit_proposed_direction` ·
`record_user_decision` · `create_or_revise_plan` · `park_branch` · `save_evidence`

**Lookups** (read-only, pulled only when a turn needs them): `get_project_snapshot`
· `get_evidence_ledger` · `get_open_research_tasks` · `get_branch_alternatives` ·
`get_next_actions_plan`

**Documents**: `ingest_pdf` · `list_indexed_documents` · `search_documents`

**Web**: `web_search` · `fetch_url`

### Research and evidence

Research is agentic: the agent always has `web_search` and `fetch_url` and
decides for itself, from each tool's description, whether it needs them. Fetched
web pages and ingested documents are **source material** — they become project
evidence only through an explicit `save_evidence` call that passes a
source-support and project-relevance check.

`web_search` defaults to the free, keyless DuckDuckGo (`ddgs`); set
`MYTHINKING_RESEARCH_RETRIEVER=tavily` with `TAVILY_API_KEY` to use Tavily
instead. Fetched content lives in `data/store.sqlite` (a LangGraph `SqliteStore`,
separate from the board). `search_documents` returns each passage under a
citation tag — `[[file.pdf p.3]]` for an ingested PDF (chunked page by page),
`[[Title]]` for a web source — and the system prompt requires those tags to be
copied verbatim into any document-grounded answer.

Retrieval embeddings (for fetched content, and for project state itself once a
project grows past `MYTHINKING_CONTEXT_RETRIEVAL_THRESHOLD` items) go through the
same OpenRouter key via `MYTHINKING_EMBEDDING_MODEL`
(default `openai/text-embedding-3-small`).

### Optional: user profile

Cross-project profile extraction (role, expertise, working style — never
sensitive personal details) is **off by default**. Set
`MYTHINKING_ENABLE_PROFILE_EXTRACTION=true` and inspect what was captured with
`uv run mythinking profile`.

### Optional: tracing

```bash
uv sync --group observability
```

Then set the `MYTHINKING_MLFLOW_*` variables in `.env` (see `.env.example`).
`mlflow` is imported lazily, so the core install stays lean.

---

## HTTP API

```bash
uv run mythinking serve       # binds 127.0.0.1:8000 by default
```

```text
GET    /health                                   liveness check
POST   /turns                                    {"message": "...", "project_id": "..."} -> AssistantTurn
POST   /turns/stream                             same body -> text/event-stream of TurnStreamEvent frames
GET    /projects?limit=20                        recent project summaries, newest first
GET    /projects/{project_id}                    full ProjectState
GET    /projects/{project_id}/documents          indexed documents for a project

# Direct edits (no agent turn). Each returns the updated ProjectState;
# KeyError -> 404, ValueError -> 400.
PATCH  /projects/{id}/north-star                 {"title": "..."}
POST   /projects/{id}/decisions                  {"choice": "...", "question?": "...", "rationale?": "...", "reversible?": true}
PATCH  /projects/{id}/decisions/{decision_id}    partial of the same fields
DELETE /projects/{id}/decisions/{decision_id}
POST   /projects/{id}/proposal/approve           commit the pending proposal verbatim
DELETE /projects/{id}/proposal                   dismiss the pending proposal
POST   /projects/{id}/next-actions               {"description": "...", "time_box_minutes?": 30}  (origin="user")
PATCH  /projects/{id}/next-actions/{action_id}   partial; also toggles completed
DELETE /projects/{id}/next-actions/{action_id}
```

`POST /turns/stream` emits one Server-Sent Event per tool the agent runs
(`{"type": "node", "node": "<tool name>"}`), then a final
`{"type": "turn", "turn": <AssistantTurn>}`. A failure after streaming has begun
arrives as a terminal `{"type": "error", "detail": "..."}` event rather than a
dropped connection.

CORS is open for the local Next.js dev server (`localhost` / `127.0.0.1` on
ports `3000` and `3001`).

---

## Frontend

An immersive workspace UI lives in [`frontend/`](frontend/) — a
Next.js / TypeScript app that talks to the API over HTTP only.

```bash
cd frontend
npm install
npm run dev
```

Run `uv run mythinking serve` in another terminal first. The app targets
`http://127.0.0.1:8000` by default; override with `NEXT_PUBLIC_API_BASE_URL`
(see `frontend/.env.local.example`). Other scripts: `npm run typecheck`,
`npm run test`, `npm run build`, `npm run generate:types`.

---

## Development

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
```

Model-dependent behavior has offline fixtures — the normal test suite never
needs a live API key.

### Project layout

```text
src/mythinking/
  config.py       Environment and OpenRouter settings
  llm.py          The only model-construction boundary
  state.py        Typed thinking and project state (Pydantic)
  persistence.py  Project snapshots and LangGraph checkpoints
  documents.py    Full-text research documents and chunks (page-tracked for PDFs)
  retrieval.py    Typed wrapper around LangGraph's SqliteStore for semantic search
  context.py      Scoped context formatting and threshold-based retrieval
  gates.py        North Star / decision / evidence structured-output gates
  board.py        Mutable state holder, mode derivation, plan staleness, frame merge
  exploration.py  Explore/converge merge and formatting service
  planning.py     Next-action planning merge/formatting service
  evidence.py     Evidence ledger merge and citation rendering
  research.py     Research-task matching and scoped evidence-import pipeline
  profile.py      User-profile merge and prompt rendering
  tools.py        The agent's tools: precondition-gated thinking tools,
                  read-only lookups, document tools, and web tools
  agents/         Specialist structured-output engines invoked inside tools
  agent.py        The single create_agent loop + context-injection middleware
  runtime.py      Turn orchestration and persistence
  prompts.py      Versioned prompt registry
  ingest.py       File upload / ingestion
  observability.py Optional MLflow tracing (lazy import)
  summary.py      Deterministic, offline session summary rendering
  api.py          HTTP API over the runtime (non-streaming + SSE)
  cli.py          init, status, smoke-model, chat, list, show, profile, serve
prompts/          Versioned prompt specifications (YAML)
evals/            Offline behavioral evaluation cases
tests/            Deterministic unit tests
frontend/         Next.js / TypeScript workspace UI (HTTP-only)
docs/             Design notes and the implementation plan
```

Each turn:

```text
load board -> run the Thinker agent (tools enforce preconditions, mutate the
board in place) -> derive display mode -> persist -> AssistantTurn
```

The chat thread persists in `data/checkpoints.sqlite` (per `project_id`), the
board in `data/state.sqlite`, and fetched/ingested documents in
`data/store.sqlite`.

---

## Contributing

Contributions are welcome — issues, discussion, and PRs alike.

1. Read [`AGENTS.md`](AGENTS.md) — the product contract and the architecture
   rules the codebase holds itself to. The two that matter most:
   **do not reintroduce a multi-agent graph or an intent classifier**, and
   **keep board-mutation correctness in deterministic tool preconditions**, not
   in prompt text.
2. [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) is the milestone
   roadmap and the record of design decisions.
3. Every behavior change ships with tests. Run `uv run ruff check .`,
   `uv run ruff format --check .`, and `uv run pytest` before opening a PR;
   for frontend changes also run `npm run typecheck && npm run test` in
   `frontend/`.
4. Prompts are versioned YAML in `prompts/`. Every behavioral instruction needs
   either an evidence entry or an explicit `product_hypothesis` label, plus an
   evaluation case in `evals/`.

Never commit API keys, conversation data, databases, or model traces.

## License

[MIT](LICENSE).
