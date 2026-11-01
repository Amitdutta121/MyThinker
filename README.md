# MyThinking

![MyThinking: a thinking partner that won't decide for you](docs/assets/banner.png)

MyThinking is an LLM thinking partner for working an idea through to a decision.
It keeps a project board for each idea: the goal (the "North Star"), the
alternatives you've considered, the decisions you've made, the evidence behind
them, and a short plan of next actions. The board lives in local SQLite, so you
can come back to a project days later and pick up where you left off.

It is a single LangGraph agent with 18 tools. There's no router or
intent classifier; the model decides which tool a turn needs. The rules that keep
the board consistent are checked in Python inside the tools, not left to the
prompt. If the model tries to commit a direction you never agreed to, the tool
refuses:

```text
commit_proposed_direction -> "BLOCKED: this turn does not explicitly authorize
committing the proposal. Present it and ask the user to confirm."
```

The agent sees that message as the tool result and has to ask you instead.

Status: a research prototype I use myself. Single user, local only, no auth.

## Install

You need Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), and an
[OpenRouter](https://openrouter.ai/settings/keys) API key.

```bash
git clone https://github.com/Amitdutta121/MyThinker.git
cd MyThinker
uv sync
cp .env.example .env   # then set OPENROUTER_API_KEY
uv run mythinking init
```

## Usage

```bash
uv run mythinking chat "I want to build an onboarding tool for restaurant staff."
uv run mythinking chat --last "What are the alternatives to video lessons?"
uv run mythinking chat --project-id <id> "Go with the checklist approach."
uv run mythinking list         # recent projects
uv run mythinking show <id>    # board summary for one project
```

Each `chat` call prints the project ID, the current mode (capture, clarify,
explore, research, converge, decide, ...) and the reply.

The model defaults to OpenRouter's `~openai/gpt-latest`. Set `OPENROUTER_MODEL`
to any slug from the [OpenRouter catalog](https://openrouter.ai/models) to pin
one. `uv run mythinking status` prints the active configuration without making
a request; `uv run mythinking smoke-model` makes one small live request.

There is also a web UI (Next.js) and an HTTP API, described below.

## How it works

On each turn the runtime loads the project board, runs the agent, saves whatever
the tools changed, and returns the reply. The agent can answer without calling
any tool, and most ordinary questions are answered that way.

The tools that change the board each check a precondition first:

| Rule | Checked in |
| --- | --- |
| Exploring alternatives needs a North Star | `explore_ideas`, `converge_ideas` |
| Converging produces a proposal, not a commitment | `converge_ideas` |
| Committing copies the exact proposal, and only if the user's message authorizes it | `commit_proposed_direction` |
| Planning needs a committed direction | `create_or_revise_plan` |
| A web page or PDF only becomes evidence if the source supports the claim and it's relevant to the project | `save_evidence` |
| Plan steps you added yourself survive re-planning | `create_or_revise_plan` |

Framing, exploring, converging, and planning each call a structured-output
model inside the tool (`src/mythinking/agents/`). They aren't separate agents
talking to each other. An earlier multi-agent version is in
[`notebooks/architecture_validation.ipynb`](notebooks/architecture_validation.ipynb);
I moved to a single agent after it.

The full tool list:

- Board changes: `set_north_star`, `explore_ideas`, `converge_ideas`,
  `commit_proposed_direction`, `record_user_decision`, `create_or_revise_plan`,
  `park_branch`, `save_evidence`
- Read-only lookups: `get_project_snapshot`, `get_evidence_ledger`,
  `get_open_research_tasks`, `get_branch_alternatives`, `get_next_actions_plan`
- Documents: `ingest_pdf`, `list_indexed_documents`, `search_documents`
- Web: `web_search`, `fetch_url`

### Research and citations

`web_search` uses DuckDuckGo by default (no key). Set
`MYTHINKING_RESEARCH_RETRIEVER=tavily` and `TAVILY_API_KEY` to use Tavily.
`search_documents` returns passages tagged `[[file.pdf p.3]]` or `[[Page title]]`,
and the system prompt requires the agent to keep those tags in its answer.

Once a project gets large (more than `MYTHINKING_CONTEXT_RETRIEVAL_THRESHOLD`
items, default 20), the board is retrieved by embedding search instead of being
pasted into the prompt whole. Embeddings go through the same OpenRouter key
(`MYTHINKING_EMBEDDING_MODEL`, default `openai/text-embedding-3-small`).

### Storage

Everything is under `data/` (`MYTHINKING_DATA_DIR`):

- `state.sqlite`: the project boards
- `checkpoints.sqlite`: chat history, one LangGraph thread per project
- `store.sqlite`: fetched pages and ingested PDFs

### Optional settings

- `MYTHINKING_ENABLE_PROFILE_EXTRACTION=true` keeps a small cross-project
  profile (role, expertise, working style). It's off by default and skips
  sensitive details. View it with `uv run mythinking profile`.
- MLflow tracing: `uv sync --group observability`, then set the
  `MYTHINKING_MLFLOW_*` variables in `.env`.

See [`.env.example`](.env.example) for the full list.

## Web UI and HTTP API

```bash
uv run mythinking serve                     # API on 127.0.0.1:8000
cd frontend && npm install && npm run dev   # UI on localhost:3000
```

The UI only talks to the API over HTTP. Point it elsewhere with
`NEXT_PUBLIC_API_BASE_URL`.

`POST /turns/stream` sends one server-sent event per tool call
(`{"type": "node", "node": "explore_ideas"}`) and then the finished turn
(`{"type": "turn", ...}`). Errors after the stream starts arrive as a final
`{"type": "error", ...}` event.

<details>
<summary>All endpoints</summary>

```text
GET    /health
POST   /turns                                    {"message": "...", "project_id": "..."} -> AssistantTurn
POST   /turns/stream                             same body -> text/event-stream
GET    /projects?limit=20                        recent projects, newest first
GET    /projects/{project_id}                    full ProjectState
GET    /projects/{project_id}/documents          indexed documents

# Direct edits, no agent turn. Each returns the updated ProjectState.
PATCH  /projects/{id}/north-star                 {"title": "..."}
POST   /projects/{id}/decisions                  {"choice": "...", "question?": "...", "rationale?": "...", "reversible?": true}
PATCH  /projects/{id}/decisions/{decision_id}
DELETE /projects/{id}/decisions/{decision_id}
POST   /projects/{id}/proposal/approve           commit the pending proposal as-is
DELETE /projects/{id}/proposal
POST   /projects/{id}/next-actions               {"description": "...", "time_box_minutes?": 30}
PATCH  /projects/{id}/next-actions/{action_id}
DELETE /projects/{id}/next-actions/{action_id}
```

CORS allows `localhost` and `127.0.0.1` on ports 3000 and 3001.

</details>

## Evals

[`evals/cases.jsonl`](evals/cases.jsonl) has 63 hand-written cases in 15
categories. A case is one or more user messages, optionally a pre-seeded board,
and two kinds of checks:

- deterministic checks on the tool calls and the board diff, e.g.
  `{"tools_include": ["converge_ideas"], "tools_exclude": ["commit_proposed_direction"]}`
- plain-language expectations scored by an LLM judge, e.g.
  "Does not create a plan from an uncommitted proposal"

The runner calls the live model, so it costs money and isn't run in CI.
`uv run pytest` only checks that the case file is well-formed.

```bash
uv run python evals/runner.py                  # deterministic checks only
uv run python evals/runner.py --judge          # also score expectations
uv run python evals/runner.py --only commit-exact-proposal
```

The case schema is documented at the top of [`evals/runner.py`](evals/runner.py).
The cases are also on Hugging Face as
[`amitdutta121/mythinking-evals`](https://huggingface.co/datasets/amitdutta121/mythinking-evals).
To regenerate and upload:

```bash
uv run python evals/export_hf.py   # writes dist/hf-dataset/
hf upload amitdutta121/mythinking-evals dist/hf-dataset --repo-type dataset
```

## Development

```bash
uv run ruff format .
uv run ruff check .
uv run pytest        # offline, no API key needed
```

Frontend: `npm run typecheck` and `npm run test` in `frontend/`.

The code is in `src/mythinking/`. `agent.py` builds the agent, `tools.py`
holds the tools and their preconditions, `runtime.py` runs a turn and saves it,
and `state.py` defines the board. Prompts are versioned YAML files in
`prompts/`. [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) records
the milestones and design decisions.

## Contributing

Issues and PRs are welcome; see [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`AGENTS.md`](AGENTS.md). Two constraints I'd like to keep: no multi-agent graph
or intent classifier, and board rules enforced in tool code rather than in
prompts. Behavior changes need tests, and prompt changes need an eval case.

## License

MIT
