"""Provider-neutral model construction through OpenRouter."""

from langchain_openai import OpenAIEmbeddings
from langchain_openrouter import ChatOpenRouter

from mythinking.config import Settings, get_settings

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def create_chat_model(
    settings: Settings | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenRouter:
    """Create the shared LangChain chat model without leaking provider details."""

    runtime = settings or get_settings()
    return ChatOpenRouter(
        model=model or runtime.openrouter_model,
        api_key=runtime.require_api_key(),
        app_url=runtime.openrouter_app_url,
        app_title=runtime.openrouter_app_title,
        temperature=runtime.temperature if temperature is None else temperature,
        max_tokens=max_tokens or runtime.max_tokens,
        max_retries=runtime.max_retries,
        openrouter_provider={"data_collection": runtime.openrouter_data_collection},
    )


def create_embeddings_model(settings: Settings | None = None) -> OpenAIEmbeddings:
    """Create the shared embeddings client.

    `langchain-openrouter` ships no embeddings class, but OpenRouter's
    embeddings endpoint is OpenAI-compatible, so `OpenAIEmbeddings` pointed at
    it reuses the same API key as chat instead of requiring a second provider.
    """

    runtime = settings or get_settings()
    return OpenAIEmbeddings(
        model=runtime.embedding_model,
        api_key=runtime.require_api_key(),
        base_url=_OPENROUTER_BASE_URL,
    )
