from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.embeddings import Embeddings
from pydantic import SecretStr

import mythinking.tools as tools_module
from mythinking.config import Settings
from mythinking.context import ContextRetriever
from mythinking.deep_research import ResearchSource
from mythinking.retrieval import list_documents, open_document_store
from mythinking.state import (
    BranchStatus,
    EvidenceItem,
    EvidenceKind,
    IdeaBranch,
    NextAction,
    ProjectState,
    ResearchTask,
)
from mythinking.tools import build_context_tools, build_research_tools


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0]


class FakeDeepResearchRunner:
    def __init__(self, sources: list[ResearchSource]) -> None:
        self.sources = sources
        self.questions_asked: list[str] = []

    def run(self, question: str) -> list[ResearchSource]:
        self.questions_asked.append(question)
        return self.sources


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("test-key"), **overrides)


@pytest.fixture
def store(tmp_path: Path):
    with open_document_store(tmp_path / "store.sqlite", FakeEmbeddings(), dimensions=1) as opened:
        yield opened


def test_build_research_tools_excludes_run_deep_research_when_disabled(store: Any) -> None:
    tools = build_research_tools("proj1", store, _settings(enable_deep_research=False))

    assert [t.name for t in tools] == ["web_search", "fetch_url"]


def test_build_research_tools_includes_run_deep_research_when_enabled(store: Any) -> None:
    tools = build_research_tools("proj1", store, _settings(enable_deep_research=True))

    assert "run_deep_research" in [t.name for t in tools]


def test_run_deep_research_tool_calls_runner_and_indexes_results(store: Any) -> None:
    runner = FakeDeepResearchRunner(
        [ResearchSource(title="A study", content="Pricing converts at 2%.", url="https://x")]
    )
    tools = build_research_tools(
        "proj1", store, _settings(enable_deep_research=True), deep_research_runner=runner
    )
    run_deep_research = next(t for t in tools if t.name == "run_deep_research")

    result = run_deep_research.invoke({"query": "pricing conversion"})

    assert runner.questions_asked == ["pricing conversion"]
    assert "Pricing converts at 2%" in result
    documents = list_documents(store, "proj1")
    assert len(documents) == 1
    assert documents[0].title == "A study"


def test_web_search_tool_dispatches_to_duckduckgo_by_default(
    store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run_web_search(query: str, settings: Settings) -> list[ResearchSource]:
        assert query == "competitor pricing"
        return [
            ResearchSource(title="Competitor page", content="They charge $10/mo.", url="https://y")
        ]

    monkeypatch.setattr(tools_module, "_run_web_search", fake_run_web_search)
    tools = build_research_tools("proj1", store, _settings())
    web_search = next(t for t in tools if t.name == "web_search")

    result = web_search.invoke({"query": "competitor pricing"})

    assert "They charge $10/mo." in result
    documents = list_documents(store, "proj1")
    assert len(documents) == 1


def test_run_web_search_uses_duckduckgo_results_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def text(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
            assert query == "test query"
            return [{"title": "T", "href": "https://z", "body": "content body"}]

    monkeypatch.setattr(tools_module, "DDGS", FakeDDGS)

    results = tools_module._run_web_search("test query", _settings())

    assert results == [ResearchSource(title="T", content="content body", url="https://z")]


def test_run_web_search_uses_tavily_when_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTavilyClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "tavily-key"

        def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
            return {"results": [{"title": "T", "url": "https://z", "content": "tavily body"}]}

    monkeypatch.setattr(tools_module, "TavilyClient", FakeTavilyClient)
    settings = _settings(research_retriever="tavily", tavily_api_key=SecretStr("tavily-key"))

    results = tools_module._run_web_search("test query", settings)

    assert results == [ResearchSource(title="T", content="tavily body", url="https://z")]


def test_fetch_url_tool_extracts_text_and_indexes(
    store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = (
        "<html><head><title>A Page</title></head><body>"
        "<script>ignored()</script><p>Real content here.</p></body></html>"
    )

    def fake_get(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(200, text=html, request=httpx.Request("GET", url))

    monkeypatch.setattr(tools_module.httpx, "get", fake_get)
    tools = build_research_tools("proj1", store, _settings())
    fetch_url = next(t for t in tools if t.name == "fetch_url")

    result = fetch_url.invoke({"url": "https://example.com/page"})

    assert "Real content here." in result
    assert "ignored()" not in result
    documents = list_documents(store, "proj1")
    assert documents[0].title == "A Page"


def test_fetch_url_tool_reports_http_errors_without_raising(
    store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_get(url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(tools_module.httpx, "get", fake_get)
    tools = build_research_tools("proj1", store, _settings())
    fetch_url = next(t for t in tools if t.name == "fetch_url")

    result = fetch_url.invoke({"url": "https://example.com/page"})

    assert "Could not fetch" in result or "no readable text" in result


def _project_state_with_notes() -> ProjectState:
    project_state = ProjectState()
    project_state.evidence = [
        EvidenceItem(claim="Users churn early", kind=EvidenceKind.FACT, source_url="https://x")
    ]
    project_state.research_tasks = [ResearchTask(question="Is there real demand?")]
    project_state.branches = [IdeaBranch(name="Newsletter", status=BranchStatus.ACTIVE)]
    project_state.next_actions = [NextAction(description="Talk to 5 users")]
    return project_state


class _FakeStore:
    def search(
        self,
        namespace: Any,
        *,
        query: Any = None,
        filter: Any = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list:
        raise AssertionError("should not query the store below the configured threshold")


def test_build_context_tools_expose_real_project_state() -> None:
    from mythinking.board import MutableStateHolder

    holder = MutableStateHolder(project_state=_project_state_with_notes())
    context_retriever = ContextRetriever(_FakeStore(), threshold=1000, top_k=3)
    tools = {t.name: t for t in build_context_tools(holder, context_retriever)}

    assert "get_project_snapshot" in tools
    assert "Users churn early" in tools["get_evidence_ledger"].invoke({"topic": "churn"})
    assert "Is there real demand?" in tools["get_open_research_tasks"].invoke({})
    assert "Newsletter" in tools["get_branch_alternatives"].invoke({})
    assert "Talk to 5 users" in tools["get_next_actions_plan"].invoke({})
