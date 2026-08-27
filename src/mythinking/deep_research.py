"""gpt-researcher integration: real multi-source web research, feature-flagged off by default.

Only `conduct_research()` + `get_research_sources()` are used -- `write_report()`
is skipped deliberately, since it produces markdown prose we don't need; the
structured `{title, content, url}` sources are all the downstream extraction
step (agents/researcher.py) requires.
"""

import asyncio
import os
from typing import Any

from pydantic import BaseModel

from mythinking.config import Settings


class ResearchSource(BaseModel):
    """One fetched source, as returned by gpt-researcher's `get_research_sources()`."""

    title: str = ""
    content: str = ""
    url: str = ""


class DeepResearchRunner:
    """Run gpt-researcher for one question and return its structured sources.

    gpt-researcher reads its own configuration from process `os.environ`, not
    from this app's `Settings` object, so `_configure_environment` sets the
    required variables immediately before constructing `GPTResearcher`.
    `Settings` is a process-wide singleton (`get_settings()`), so writing the
    same values on every call is idempotent, not a race, even under FastAPI's
    sync threadpool.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, question: str) -> list[ResearchSource]:
        self._configure_environment()
        return asyncio.run(self._run_async(question))

    async def _run_async(self, question: str) -> list[ResearchSource]:
        from gpt_researcher import GPTResearcher

        researcher = GPTResearcher(query=question, report_type="research_report")
        await researcher.conduct_research()
        sources: list[dict[str, Any]] = researcher.get_research_sources()
        return [ResearchSource.model_validate(source) for source in sources]

    def _configure_environment(self) -> None:
        os.environ["OPENROUTER_API_KEY"] = self.settings.require_api_key()
        os.environ["EMBEDDING"] = f"openrouter:{self.settings.embedding_model}"
        model = f"openrouter:{self.settings.openrouter_model}"
        os.environ["FAST_LLM"] = model
        os.environ["SMART_LLM"] = model
        os.environ["STRATEGIC_LLM"] = model
        os.environ["RETRIEVER"] = self.settings.research_retriever
        if self.settings.research_retriever == "tavily":
            os.environ["TAVILY_API_KEY"] = self.settings.require_tavily_key()
