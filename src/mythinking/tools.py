"""Tools for the agentic Researcher and Supervisor.

No manual gate decides which of these are visible to a model at any given
moment (besides `enable_deep_research` deciding whether `run_deep_research`
is even in the list at all -- see its docstring below). Tool *selection*
within whatever list is handed to `create_agent` is the model's own
judgment, guided by each tool's description -- the idiomatic LangChain
pattern, not a hand-coded keyword check.
"""

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain_core.tools import BaseTool, tool
from langgraph.store.sqlite import SqliteStore
from tavily import TavilyClient

from mythinking.config import Settings
from mythinking.context import ContextRetriever
from mythinking.deep_research import DeepResearchRunner, ResearchSource
from mythinking.documents import Document, DocumentChunk, chunk_text
from mythinking.exploration import format_branch_alternatives
from mythinking.planning import format_next_actions
from mythinking.research import format_open_research_tasks
from mythinking.retrieval import index_chunk, index_document
from mythinking.state import ProjectState

_FETCH_TIMEOUT_SECONDS = 15.0
_MAX_RESULT_CHARS = 4000


def build_research_tools(
    project_id: str,
    store: SqliteStore,
    settings: Settings,
    research_task_id: str = "",
    *,
    deep_research_runner: DeepResearchRunner | None = None,
) -> list[BaseTool]:
    """Build this turn's research toolset, closing over the current project/store."""

    runner = deep_research_runner or DeepResearchRunner(settings)

    @tool
    def web_search(query: str) -> str:
        """Search the web for one specific, narrower fact or source.

        Cheaper and faster than run_deep_research -- use this for a
        targeted lookup (e.g. one fact, one comparison), not a
        comprehensive multi-source report.
        """
        results = _run_web_search(query, settings)
        _store_and_index_sources(project_id, store, research_task_id, results)
        return _summarize_sources_for_model(results)

    @tool
    def fetch_url(url: str) -> str:
        """Fetch and read one specific web page's text content.

        Use this for a URL the user pasted, or one found via web_search.
        """
        source = _fetch_page(url)
        _store_and_index_sources(project_id, store, research_task_id, [source])
        return source.content[:_MAX_RESULT_CHARS] or "The page returned no readable text."

    @tool
    def run_deep_research(query: str) -> str:
        """Run a thorough, multi-source live web-research pass.

        Expensive and slow. Only call this when the user has explicitly and
        unambiguously asked for deep, thorough, or extensive research (e.g.
        "do a deep research on this", "search the web thoroughly for X").
        For a narrower question, prefer web_search or fetch_url, or answer
        directly if you already have enough information.
        """
        sources = runner.run(query)
        _store_and_index_sources(project_id, store, research_task_id, sources)
        return _summarize_sources_for_model(sources)

    tools: list[BaseTool] = [web_search, fetch_url]
    if settings.enable_deep_research:
        tools.append(run_deep_research)
    return tools


def build_context_tools(
    project_state: ProjectState,
    context_retriever: ContextRetriever,
) -> list[BaseTool]:
    """Read-only lookups over this project's own saved state. No internet access."""

    @tool
    def get_evidence_ledger(topic: str = "") -> str:
        """Look up facts, inferences, and hypotheses already saved for this project.

        Pass a short topic/question describing what you're looking for.
        """
        query = topic or project_state.north_star.title
        return context_retriever.select_evidence(project_state, query)

    @tool
    def get_open_research_tasks() -> str:
        """List this project's open research questions that haven't been answered yet."""
        return format_open_research_tasks(project_state)

    @tool
    def get_branch_alternatives() -> str:
        """List the alternative directions currently on the table for this project."""
        return format_branch_alternatives(project_state)

    @tool
    def get_next_actions_plan() -> str:
        """List the next actions already planned for this project, if any."""
        return format_next_actions(project_state)

    return [
        get_evidence_ledger,
        get_open_research_tasks,
        get_branch_alternatives,
        get_next_actions_plan,
    ]


def _run_web_search(query: str, settings: Settings) -> list[ResearchSource]:
    if settings.research_retriever == "tavily":
        client = TavilyClient(api_key=settings.require_tavily_key())
        response = client.search(query, max_results=5)
        return [
            ResearchSource(
                title=result.get("title", ""),
                content=result.get("content", ""),
                url=result.get("url", ""),
            )
            for result in response.get("results", [])
        ]

    results = DDGS().text(query, max_results=5)
    return [
        ResearchSource(
            title=result.get("title", ""),
            content=result.get("body", ""),
            url=result.get("href", ""),
        )
        for result in results
    ]


def _fetch_page(url: str) -> ResearchSource:
    try:
        response = httpx.get(url, follow_redirects=True, timeout=_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return ResearchSource(title="", content=f"Could not fetch {url}: {exc}", url=url)

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    return ResearchSource(title=title, content=text, url=url)


def _summarize_sources_for_model(sources: list[ResearchSource]) -> str:
    if not sources:
        return "No results found."
    lines = []
    for source in sources:
        snippet = source.content[:500]
        lines.append(f"- {source.title or source.url} ({source.url}): {snippet}")
    return "\n".join(lines)


def _store_and_index_sources(
    project_id: str,
    store: SqliteStore,
    research_task_id: str,
    sources: list[ResearchSource],
) -> None:
    for source in sources:
        if not source.content.strip():
            continue
        document = Document(
            project_id=project_id,
            research_task_id=research_task_id,
            source_url=source.url,
            title=source.title,
            content=source.content,
        )
        index_document(store, project_id, document)
        for chunk_index, text in enumerate(chunk_text(source.content)):
            chunk = DocumentChunk(
                document_id=document.id,
                project_id=project_id,
                chunk_index=chunk_index,
                text=text,
            )
            index_chunk(store, project_id, chunk)


__all__ = ["build_context_tools", "build_research_tools"]
