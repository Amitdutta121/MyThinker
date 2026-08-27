import os

import pytest
from pydantic import SecretStr

from mythinking.config import Settings
from mythinking.deep_research import DeepResearchRunner, ResearchSource

_DEEP_RESEARCH_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "EMBEDDING",
    "FAST_LLM",
    "SMART_LLM",
    "STRATEGIC_LLM",
    "RETRIEVER",
    "TAVILY_API_KEY",
)


@pytest.fixture(autouse=True)
def _clean_deep_research_env() -> None:
    """`_configure_environment` mutates real `os.environ` directly, outside monkeypatch's
    tracking, so leftover values from one test would otherwise leak into the next."""

    for var in _DEEP_RESEARCH_ENV_VARS:
        os.environ.pop(var, None)
    yield
    for var in _DEEP_RESEARCH_ENV_VARS:
        os.environ.pop(var, None)


def test_configure_environment_sets_openrouter_provider_variables() -> None:
    settings = Settings(
        _env_file=None,
        openrouter_api_key=SecretStr("test-key"),
        openrouter_model="test/chat-model",
        embedding_model="test/embed-model",
    )
    runner = DeepResearchRunner(settings)

    runner._configure_environment()

    assert os.environ["OPENROUTER_API_KEY"] == "test-key"
    assert os.environ["EMBEDDING"] == "openrouter:test/embed-model"
    assert os.environ["FAST_LLM"] == "openrouter:test/chat-model"
    assert os.environ["SMART_LLM"] == "openrouter:test/chat-model"
    assert os.environ["STRATEGIC_LLM"] == "openrouter:test/chat-model"
    assert os.environ["RETRIEVER"] == "duckduckgo"
    assert "TAVILY_API_KEY" not in os.environ


def test_configure_environment_sets_tavily_key_when_selected() -> None:
    settings = Settings(
        _env_file=None,
        openrouter_api_key=SecretStr("test-key"),
        research_retriever="tavily",
        tavily_api_key=SecretStr("tavily-key"),
    )
    runner = DeepResearchRunner(settings)

    runner._configure_environment()

    assert os.environ["RETRIEVER"] == "tavily"
    assert os.environ["TAVILY_API_KEY"] == "tavily-key"


def test_configure_environment_requires_tavily_key_when_selected() -> None:
    settings = Settings(
        _env_file=None,
        openrouter_api_key=SecretStr("test-key"),
        research_retriever="tavily",
    )
    runner = DeepResearchRunner(settings)

    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        runner._configure_environment()


def test_run_delegates_to_async_implementation_and_parses_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, openrouter_api_key=SecretStr("test-key"))
    runner = DeepResearchRunner(settings)
    monkeypatch.setattr(runner, "_configure_environment", lambda: None)

    async def fake_run_async(question: str) -> list[ResearchSource]:
        assert question == "does anyone want this?"
        return [ResearchSource(title="A source", content="some content", url="https://example.com")]

    monkeypatch.setattr(runner, "_run_async", fake_run_async)

    sources = runner.run("does anyone want this?")

    assert sources == [
        ResearchSource(title="A source", content="some content", url="https://example.com")
    ]
