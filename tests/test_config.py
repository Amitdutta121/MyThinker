from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from mythinking.config import Settings


def test_settings_defaults_do_not_require_a_key() -> None:
    settings = Settings(_env_file=None)

    assert settings.openrouter_model == "~openai/gpt-latest"
    assert settings.openrouter_data_collection == "deny"
    assert settings.state_database_path == Path("data/state.sqlite")
    assert settings.store_database_path == Path("data/store.sqlite")
    assert not settings.has_api_key
    assert settings.enable_profile_extraction is False
    assert settings.research_retriever == "duckduckgo"
    assert settings.embedding_model == "openai/text-embedding-3-small"
    assert settings.embedding_dimensions == 1536
    assert settings.context_retrieval_threshold == 20
    assert settings.context_retrieval_top_k == 6
    assert not settings.has_tavily_key


def test_profile_extraction_can_be_enabled_via_env_alias() -> None:
    settings = Settings(_env_file=None, enable_profile_extraction=True)

    assert settings.enable_profile_extraction is True


def test_require_api_key_returns_secret_value() -> None:
    settings = Settings(openrouter_api_key=SecretStr("test-key"), _env_file=None)

    assert settings.require_api_key() == "test-key"


def test_require_api_key_has_actionable_error() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        settings.require_api_key()


def test_invalid_data_collection_policy_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(openrouter_data_collection="sometimes", _env_file=None)


def test_invalid_research_retriever_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(research_retriever="bing", _env_file=None)


def test_require_tavily_key_returns_secret_value() -> None:
    settings = Settings(tavily_api_key=SecretStr("tavily-key"), _env_file=None)

    assert settings.require_tavily_key() == "tavily-key"


def test_require_tavily_key_has_actionable_error() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        settings.require_tavily_key()
