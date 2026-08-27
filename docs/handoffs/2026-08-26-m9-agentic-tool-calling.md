# Session Handoff

## Completed

- Milestone `M9` completed: agentic tool-calling for research and chat
  replies. Full design is in `docs/IMPLEMENTATION_PLAN.md`'s new `M9`
  section.
- Motivation: the user wanted the chat window to feel agentic like
  ChatGPT's -- the assistant decides for itself, mid-turn, whether it
  already has enough information or needs to look something up, rather
  than following one fixed pipeline every time.
- **This milestone deliberately reverses a mechanism built earlier in the
  same session, as part of `M8`'s own follow-up work.** That earlier step
  added `research.detect_deep_research_request` -- a hand-rolled Python
  keyword check deciding whether the costly gpt-researcher pass was allowed
  to run. That was a reasonable stopgap at the time, but reading
  `docs.langchain.com/oss/python/langchain/agents` and testing
  `create_agent` directly this session confirmed it isn't the idiomatic
  mechanism: LangChain's actual pattern is to define each tool with a clear
  docstring and let the model's own tool-selection judgment decide, which
  it's specifically trained to do from a tool's description. So the
  Python-level gate was removed; the same intent ("only run the expensive
  pass on an explicit, unambiguous ask") now lives inside `run_deep_research`'s
  own docstring instead.
- **gpt-researcher stays** as a dependency (contrary to an earlier draft of
  this plan that considered removing it) -- it's wrapped as one tool
  (`run_deep_research`) among several, not something the user wanted
  removed.
- `src/mythinking/tools.py` (new):
  - `build_research_tools(project_id, store, settings, research_task_id="", *, deep_research_runner=None) -> list[BaseTool]`
    -- `web_search` (DuckDuckGo default via the `ddgs` package -- the
    successor to the now-deprecated `duckduckgo_search`, swapped mid-session
    after a runtime deprecation warning surfaced; Tavily opt-in via
    `tavily-python`), `fetch_url` (`httpx` + BeautifulSoup text extraction),
    and `run_deep_research` (wraps the unchanged `deep_research.DeepResearchRunner`)
    -- included in the returned list only when `settings.enable_deep_research`
    is `True`. All three chunk and index whatever they fetch into the shared
    `SqliteStore` (reusing `documents.chunk_text`/`retrieval.index_document`/
    `index_chunk` from `M8`), so content found in one turn stays reusable
    later at no extra cost.
  - `build_context_tools(project_state, context_retriever) -> list[BaseTool]`
    -- `get_evidence_ledger`, `get_open_research_tasks`,
    `get_branch_alternatives`, `get_next_actions_plan`, each just wrapping an
    existing `M8` formatter/`ContextRetriever` method as a callable tool
    instead of always pre-rendering it. No internet-access tools here.
- `src/mythinking/agents/researcher.py`: rewritten around
  `langchain.agents.create_agent`. `analyze(project_state, user_message,
  research_task=None) -> ResearcherAnalysis` -- **back to its original
  3-argument shape** (the `deep` parameter added for the now-superseded
  gate is gone; there's no separate code branch for it anymore). Every
  call builds the full toolset via `build_research_tools(...)` and lets the
  model decide. `response_format=ResearcherAnalysis` means
  `result["structured_response"]` is already the validated typed object
  `ResearchImporter.merge` expects -- that merge function, and its
  `graph.py` call site, needed zero changes. `ModelCallLimitMiddleware(run_limit=6)`
  and `ToolCallLimitMiddleware(tool_name="run_deep_research", run_limit=1)`
  cap the loop. Constructor gains `settings`, drops the direct
  `deep_research_runner` dependency (now constructed inside `tools.py`).
- `src/mythinking/agents/supervisor.py`: `respond(...)` keeps its exact
  external signature and all existing post-processing logic (default
  question injection per mode, branch-confirmation message). The core call
  is now `create_agent(model, tools=build_context_tools(...),
  response_format=SupervisorReply, middleware=[ModelCallLimitMiddleware(run_limit=4)])`.
  Constructor gains `context_retriever`.
- `prompts/researcher.v4.yaml` (new, same prompt id -- there's only one
  path now, not a shallow/deep split, so this is a plain version bump):
  instructs the model to weigh the pre-rendered `existing_evidence_ledger`/
  `retrieved_context` first, then decide for itself whether a tool call is
  needed, and to only call `run_deep_research` on an explicit, unambiguous
  ask (reinforcing what the tool's own docstring already says).
  `researcher.v3.yaml` stays on disk, no longer the active version.
- `prompts/lead_partner.v9.yaml` (new): drops the pre-rendered
  `{evidence_ledger}`/`{branch_alternatives}`/`{open_research_tasks}`/
  `{next_actions_plan}` blocks (now tool-fetchable) but keeps
  `{project_context}` (north star/mode/active branch -- small, always
  relevant, an agent could simply forget to call it) and every other
  turn-specific analysis block exactly as `v8` had them.
- Reverted, as a deliberate consequence of the mechanism this milestone
  supersedes: `state.py`'s `ResearchIntent.deep` field,
  `research.py`'s `detect_deep_research_request`/`_DEEP_RESEARCH_TRIGGERS`,
  and their wiring in `graph.py`'s `_classify_intent_node`/`_research_node`.
- `src/mythinking/runtime.py`: `ThinkingRuntime`'s store/`ContextRetriever`
  setup (from `M8`, previously gated behind `enable_deep_research`) is now
  built whenever a real `Researcher` *or* a real `SupervisorAgent` is about
  to be constructed (i.e., whenever either isn't already overridden by a
  caller/test double) -- because the Supervisor now needs a
  `ContextRetriever` on every single turn, not just research turns. A real
  `Researcher` is now constructed unconditionally (like every other
  specialist) rather than only when `enable_deep_research` was on --
  `enable_deep_research` no longer gates *whether the Researcher exists*,
  only whether `run_deep_research` is in its toolset.
- **Real behavior change from `M8`, worth being explicit about**: since
  `web_search`/`fetch_url` are always in the Researcher's toolset whenever
  it runs at all (no flag gates them -- a single targeted search or page
  fetch didn't seem to warrant a second toggle), a research-intent turn can
  now make a real network call even with `enable_deep_research=False`. Under
  `M8`, a non-"deep" research turn made zero network calls, guaranteed.
  Under `M9`, that guarantee only holds for `run_deep_research` specifically.
- `pyproject.toml`: kept `gpt-researcher`; added `beautifulsoup4`, `ddgs`
  (not `duckduckgo-search` -- see above), `tavily-python`; moved `httpx`
  from the dev group to main dependencies (removing the now-duplicate dev
  entry).
- Tests: reused the `FakeMessagesListChatModel` + `bind_tools`-as-no-op
  pattern (`FakeToolCallingModel`, duplicated per file per this repo's
  existing convention) verified empirically this session -- `create_agent`'s
  `response_format` mechanism turns out to register a synthetic tool named
  after the schema class; scripting a final `tool_calls=[{"name":
  SchemaClassName, ...}]` response is how a test deterministically drives
  the structured-response path.
  - `tests/test_tools.py` (new): both factories and all three/four tool
    functions, using fakes for `DDGS`/`TavilyClient`/`httpx.get` -- no live
    network call.
  - `tests/test_researcher_agent.py` (rewritten): the model answering
    directly with no tool call, calling `web_search` then answering,
    recovering gracefully when it naively calls the disabled
    `run_deep_research`, and the `ModelCallLimitMiddleware`-triggered
    empty-analysis fallback.
  - `tests/test_supervisor.py` (rewritten): all the existing default-question/
    branch-confirmation post-processing tests, now via a single scripted
    `SupervisorReply`-tool-call response; a new test proving the tool-calling
    plumbing itself (a scripted `get_evidence_ledger` call resolves against a
    real, bound tool rather than erroring); a fallback-message test for the
    loop-ends-without-a-reply case.
  - `tests/test_research.py`/`tests/test_graph.py`/`tests/test_runtime.py`:
    reverted the `deep`-flag-specific tests/fakes added for the now-superseded
    mechanism back to their pre-that-change shape.
  - `tests/test_prompts.py`: version assertions updated (`lead_partner` v9,
    new `researcher` v4 assertion).
- Commands run:
  - `uv add "duckduckgo-search" "beautifulsoup4" "tavily-python"`, then
    swapped to `uv add ddgs` / `uv remove duckduckgo-search` after a
    deprecation warning surfaced mid-session (confirmed API-identical: same
    `title`/`href`/`body` result keys)
  - `uv run ruff format .`
  - `uv run ruff check .` (clean on every file touched; the one pre-existing
    `cli.py` `SIM105` finding predates this session and is unrelated)
  - `uv run pytest` -- full suite green, repeated 3x plus once with
    `-W error::RuntimeWarning` to positively confirm no live network calls
    slipped into the suite
  - Manual smoke test: `ThinkingRuntime` construction with a dummy API key
    and no agent overrides -- confirmed a real `Researcher`/`SupervisorAgent`
    and a real `SqliteStore` all wire together without error; both new
    prompt versions (`researcher` v4, `lead_partner` v9) render successfully
    with representative context via `PromptRegistry` directly

## Decisions locked

- Active branch for the session: `m2-drift-control-foundation`
- **No manual Python gate decides which tools exist for a given message.**
  Tool *selection* is entirely the model's judgment, guided by each tool's
  own docstring -- confirmed as the actual LangChain-documented pattern, not
  assumed.
- **`enable_deep_research` now gates one specific tool
  (`run_deep_research`), not "does the Researcher run at all" and not
  "are any tools available."** `web_search`/`fetch_url` are unconditional
  whenever the Researcher specialist runs (see the behavior-change note
  above -- deliberate, not accidental).
- **The Supervisor's context tools are read-only and internet-free by
  design** -- `build_context_tools` never includes `web_search`/`fetch_url`/
  `run_deep_research`. Internet access stays reachable only through the
  separately-routed Researcher path.
- **`response_format=<schema>` is the reconciliation point** between an
  autonomous, variable-length tool loop and this codebase's typed-output-
  then-deterministic-merge discipline. Every call site downstream of
  `Researcher.analyze()`/`SupervisorAgent.respond()` needed zero changes
  because of this.
- **A `create_agent` loop that ends without ever producing the expected
  typed tool call must degrade to a safe fallback, not crash.** For
  `ResearcherAnalysis` (all fields defaulted), that's an empty analysis. For
  `SupervisorReply` (`message` has `min_length=1`, no default), that's a
  fixed apologetic fallback string -- verified this actually happens via a
  test that scripts 10 tool-only responses in a row, past
  `ModelCallLimitMiddleware`'s cap.

## Open issues

- **Deprecation risk carried forward from `M8`, now resolved differently
  than expected**: `M8`'s handoff didn't anticipate `duckduckgo_search`
  itself being deprecated mid-project in favor of `ddgs`. Both are the same
  maintainer's package under a new name with an identical API surface
  (confirmed by reading the `ddgs` source directly), so this was a
  same-session swap, not a lingering risk -- but worth knowing the search
  dependency's name if it comes up again.
- **`fetch_url`'s text extraction is simple, not a full readability
  pipeline.** `BeautifulSoup(...).get_text()` after stripping `<script>`/
  `<style>` will still include navigation/boilerplate text on many real
  pages. Stated as a known limitation in `tools.py`'s own code, not hidden --
  a future slice could swap in a proper readability/boilerplate-removal
  library if this proves to matter in practice.
- **No per-tool telemetry or cost tracking.** `ModelCallLimitMiddleware`/
  `ToolCallLimitMiddleware` cap the *number* of calls, but nothing records
  how often `run_deep_research` actually fires, or what it costs, across
  real usage -- worth adding if usage-based tuning of the limits becomes
  necessary.
- **The Supervisor's context tools were designed to mirror the shallow,
  full-list `format_*` formatters, not `ContextRetriever`'s threshold-based
  retrieval for evidence.** `get_evidence_ledger` calls
  `context_retriever.select_evidence(...)`, which *does* get the
  threshold-based behavior from `M8`, but `get_open_research_tasks`/
  `get_branch_alternatives`/`get_next_actions_plan` call the plain,
  always-full formatters directly, not `ContextRetriever`'s (as-yet-unused)
  `select_research_tasks`/`select_decisions` methods. This mirrors `M8`'s own
  already-noted gap (the threshold mechanism isn't wired everywhere it
  plausibly could be) rather than closing it.

## Next best task

- Wire `ContextRetriever.select_research_tasks` into `get_open_research_tasks`
  (closing the gap noted above) once a project has enough research tasks
  for it to matter in practice.
- Consider a proper readability/boilerplate-removal step for `fetch_url` if
  real usage shows the simple BeautifulSoup extraction pulling in too much
  page noise.
- A frontend surface for what the Researcher/Supervisor actually looked up
  mid-turn (which tool, what it returned) -- currently invisible beyond the
  final answer; would help build trust in the agentic behavior.
