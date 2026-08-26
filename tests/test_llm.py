from unittest.mock import patch

from pydantic import SecretStr

from mythinking.config import Settings
from mythinking.llm import create_chat_model


def test_model_factory_uses_openrouter_configuration() -> None:
    settings = Settings(
        openrouter_api_key=SecretStr("test-key"),
        openrouter_model="test/provider-model",
        openrouter_app_url="https://example.test",
        openrouter_app_title="Test App",
        _env_file=None,
    )

    with patch("mythinking.llm.ChatOpenRouter") as model_class:
        create_chat_model(settings, temperature=0, max_tokens=512)

    model_class.assert_called_once_with(
        model="test/provider-model",
        api_key="test-key",
        app_url="https://example.test",
        app_title="Test App",
        temperature=0,
        max_tokens=512,
        max_retries=2,
        openrouter_provider={"data_collection": "deny"},
    )
