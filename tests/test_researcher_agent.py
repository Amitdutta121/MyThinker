from pathlib import Path
from typing import Any

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

import mythinking.tools as tools_module
from mythinking.agents.researcher import Researcher
from mythinking.config import Settings
from mythinking.context import ContextRetriever
from mythinking.deep_research import ResearchSource
from mythinking.prompts import PromptRegistry
from mythinking.retrieval import list_documents, open_document_store
from mythinking.state import ProjectState

PROMPT_DIR = Path(__file__).parents[1] / "prompts"


class FakeToolCallingModel(FakeMessagesListChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeToolCallingModel":
        return self


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0 if "pricing" in text.lower() else 0.0, 1.0]


def _analysis_response(
    *, answer: str = "", task_resolved: bool = False, call_id: str = "final"
) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "ResearcherAnalysis",
                "args": {"answer": answer, "task_resolved": task_resolved, "findings_to_add": []},
                "id": call_id,
            }
        ],
    )


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("test-key"), **overrides)


@pytest.fixture
def store(tmp_path: Path):
    with open_document_store(tmp_path / "store.sqlite", FakeEmbeddings(), dimensions=2) as opened:
        yield opened


def _agent(model: FakeToolCallingModel, store: Any, settings: Settings) -> Researcher:
    context_retriever = ContextRetriever(store, threshold=20, top_k=5)
    return Researcher(PromptRegistry(PROMPT_DIR), model, context_retriever, store, settings)


def test_researcher_answers_directly_when_it_already_has_enough(store: Any) -> None:
    """The model can decide, on its own, that no tool call is needed."""

    model = FakeToolCallingModel(
        responses=[_analysis_response(answer="Already known.", task_resolved=True)]
    )
    agent = _agent(model, store, _settings())
    project_state = ProjectState()

    result = agent.analyze(project_state, "can you look into whether that's true?")

    assert result.answer == "Already known."
    assert result.task_resolved is True


def test_researcher_can_call_web_search_before_answering(
    store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_web_search(query: str, settings: Settings) -> list[ResearchSource]:
        assert query == "pricing conversion"
        return [
            ResearchSource(
                title="Pricing study", content="Pricing pages convert at 2%.", url="https://x"
            )
        ]

    monkeypatch.setattr(tools_module, "_run_web_search", fake_web_search)

    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "web_search", "args": {"query": "pricing conversion"}, "id": "1"}
                ],
            ),
            _analysis_response(answer="Pricing converts at 2%.", task_resolved=True),
        ]
    )
    agent = _agent(model, store, _settings())
    project_state = ProjectState()

    result = agent.analyze(project_state, "what's our pricing conversion?")

    assert result.answer == "Pricing converts at 2%."
    documents = list_documents(store, project_state.project_id)
    assert len(documents) == 1
    assert documents[0].title == "Pricing study"


def test_researcher_recovers_gracefully_when_run_deep_research_is_disabled(
    store: Any,
) -> None:
    """`run_deep_research` is only bound when enable_deep_research is True
    (verified directly in test_tools.py). Here: even if the model naively
    tries to call it anyway while disabled, the loop reports the error back
    and lets the model recover instead of crashing."""

    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "run_deep_research", "args": {"query": "x"}, "id": "1"}],
            ),
            _analysis_response(answer="recovered"),
        ]
    )
    agent = _agent(model, store, _settings(enable_deep_research=False))
    project_state = ProjectState()

    result = agent.analyze(project_state, "do a deep research on this")

    assert result.answer == "recovered"


def test_researcher_falls_back_to_empty_analysis_when_the_loop_ends_without_one(
    store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ModelCallLimitMiddleware can end the loop before a ResearcherAnalysis
    tool call is ever made -- every field on that schema defaults, so an
    empty analysis is the honest fallback rather than a crash."""

    monkeypatch.setattr(tools_module, "_run_web_search", lambda query, settings: [])
    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "web_search", "args": {"query": "x"}, "id": str(i)}],
            )
            for i in range(10)
        ]
    )
    agent = _agent(model, store, _settings())
    project_state = ProjectState()

    result = agent.analyze(project_state, "keep searching forever")

    assert result.task_resolved is False
    assert result.findings_to_add == []
