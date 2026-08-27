"""Application settings loaded from environment variables and `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with OpenRouter as the model provider."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    openrouter_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENROUTER_API_KEY",
    )
    openrouter_model: str = Field(
        default="~openai/gpt-latest",
        validation_alias="OPENROUTER_MODEL",
    )
    openrouter_app_url: str = Field(
        default="http://localhost:8501",
        validation_alias="OPENROUTER_APP_URL",
    )
    openrouter_app_title: str = Field(
        default="MyThinking",
        validation_alias="OPENROUTER_APP_TITLE",
    )
    openrouter_data_collection: Literal["allow", "deny"] = Field(
        default="deny",
        validation_alias="OPENROUTER_DATA_COLLECTION",
    )

    data_dir: Path = Field(default=Path("data"), validation_alias="MYTHINKING_DATA_DIR")
    prompt_dir: Path = Field(
        default=Path("prompts"),
        validation_alias="MYTHINKING_PROMPT_DIR",
    )
    max_tokens: int = Field(
        default=4096,
        ge=256,
        validation_alias="MYTHINKING_MAX_TOKENS",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        validation_alias="MYTHINKING_MAX_RETRIES",
    )
    temperature: float = Field(
        default=0.2,
        ge=0,
        le=2,
        validation_alias="MYTHINKING_TEMPERATURE",
    )
    enable_profile_extraction: bool = Field(
        default=False,
        validation_alias="MYTHINKING_ENABLE_PROFILE_EXTRACTION",
    )
    embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        validation_alias="MYTHINKING_EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(
        default=1536,
        ge=1,
        validation_alias="MYTHINKING_EMBEDDING_DIMENSIONS",
    )
    context_retrieval_threshold: int = Field(
        default=20,
        ge=1,
        validation_alias="MYTHINKING_CONTEXT_RETRIEVAL_THRESHOLD",
    )
    context_retrieval_top_k: int = Field(
        default=6,
        ge=1,
        validation_alias="MYTHINKING_CONTEXT_RETRIEVAL_TOP_K",
    )
    enable_deep_research: bool = Field(
        default=False,
        validation_alias="MYTHINKING_ENABLE_DEEP_RESEARCH",
    )
    research_retriever: Literal["duckduckgo", "tavily"] = Field(
        default="duckduckgo",
        validation_alias="MYTHINKING_RESEARCH_RETRIEVER",
    )
    tavily_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="TAVILY_API_KEY",
    )

    @property
    def state_database_path(self) -> Path:
        return self.data_dir / "state.sqlite"

    @property
    def checkpoint_database_path(self) -> Path:
        return self.data_dir / "checkpoints.sqlite"

    @property
    def store_database_path(self) -> Path:
        return self.data_dir / "store.sqlite"

    @property
    def has_api_key(self) -> bool:
        return bool(self.openrouter_api_key and self.openrouter_api_key.get_secret_value())

    def require_api_key(self) -> str:
        if not self.has_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not configured. Copy .env.example to .env and add the key."
            )
        assert self.openrouter_api_key is not None
        return self.openrouter_api_key.get_secret_value()

    @property
    def has_tavily_key(self) -> bool:
        return bool(self.tavily_api_key and self.tavily_api_key.get_secret_value())

    def require_tavily_key(self) -> str:
        if not self.has_tavily_key:
            raise RuntimeError(
                "TAVILY_API_KEY is not configured. Set it in .env or switch "
                "MYTHINKING_RESEARCH_RETRIEVER to 'duckduckgo'."
            )
        assert self.tavily_api_key is not None
        return self.tavily_api_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
