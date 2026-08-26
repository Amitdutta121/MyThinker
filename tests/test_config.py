from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from mythinking.config import Settings


def test_settings_defaults_do_not_require_a_key() -> None:
    settings = Settings(_env_file=None)

    assert settings.openrouter_model == "~openai/gpt-latest"
    assert settings.openrouter_data_collection == "deny"
    assert settings.state_database_path == Path("data/state.sqlite")
    assert not settings.has_api_key


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
