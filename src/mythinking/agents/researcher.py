"""Researcher specialist for answering one scoped, evidence-backed research question.

An agentic `create_agent` loop, not a fixed pipeline: the model decides for
itself, per turn, whether it already has enough information or needs to
call `web_search`, `fetch_url`, or (when `Settings.enable_deep_research` is
on) `run_deep_research` -- guided entirely by each tool's own docstring, not
a hand-coded keyword gate. `response_format=ResearcherAnalysis` reconciles
that autonomous loop with the rest of this codebase's typed-output
contract: `result["structured_response"]` is a validated `ResearcherAnalysis`
just like the old single-shot call produced, so `ResearchImporter.merge`
and its `graph.py` call site never change.
"""

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langgraph.store.sqlite import SqliteStore
from pydantic import BaseModel

from mythinking.config import Settings
from mythinking.context import ContextRetriever
from mythinking.prompts import PromptRegistry
from mythinking.state import ProjectState, ResearcherAnalysis, ResearchTask
from mythinking.tools import build_research_tools

_MODEL_CALL_LIMIT = 6
_DEEP_RESEARCH_CALL_LIMIT = 1


class Researcher:
    """Run an agentic tool-calling loop to answer one scoped research question."""

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        context_retriever: ContextRetriever,
        store: SqliteStore,
        settings: Settings,
        *,
        prompt_id: str = "researcher",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.context_retriever = context_retriever
        self.store = store
        self.settings = settings
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def analyze(
        self,
        project_state: ProjectState,
        user_message: str,
        research_task: ResearchTask | None = None,
    ) -> ResearcherAnalysis:
        question = research_task.question if research_task else user_message
        research_task_id = research_task.id if research_task else ""

        retrieved_context = self.context_retriever.select_document_chunks(
            project_state.project_id, question, top_k=8
        )
        existing_evidence_ledger = self.context_retriever.select_evidence(project_state, question)

        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "research_question": question,
                "retrieved_context": retrieved_context,
                "existing_evidence_ledger": existing_evidence_ledger,
                "user_message": user_message,
            }
        )

        tools = build_research_tools(
            project_state.project_id,
            self.store,
            self.settings,
            research_task_id,
        )
        agent = create_agent(
            self.model,
            tools=tools,
            system_prompt=rendered,
            response_format=ResearcherAnalysis,
            middleware=[
                ModelCallLimitMiddleware(run_limit=_MODEL_CALL_LIMIT, exit_behavior="end"),
                ToolCallLimitMiddleware(
                    tool_name="run_deep_research",
                    run_limit=_DEEP_RESEARCH_CALL_LIMIT,
                ),
            ],
        )
        result = agent.invoke({"messages": [("user", question)]})
        structured = result.get("structured_response")
        if structured is None:
            # The model-call cap (ModelCallLimitMiddleware) can end the loop
            # before the model ever emits the ResearcherAnalysis-shaped tool
            # call -- every field defaults, so an empty analysis is a safe,
            # honest "found nothing conclusive" fallback rather than a crash.
            return ResearcherAnalysis()
        return _validate_model_output(structured, ResearcherAnalysis)


def _validate_model_output(payload: Any, schema: type[BaseModel]) -> BaseModel:
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)
