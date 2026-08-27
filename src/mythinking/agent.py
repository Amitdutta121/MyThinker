"""The single Thinker agent: one `create_agent` loop whose tools are the router.

Replaces the retired LangGraph workflow (`graph.py`) and the multi-parameter
`SupervisorAgent`. Routing is the model's own tool selection; correctness comes
from deterministic preconditions inside each tool (`tools.build_thinking_tools`).
A `wrap_model_call` middleware appends the authoritative project-status block to
the system prompt before every model call.
"""

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    wrap_model_call,
)
from langchain_core.tools import BaseTool

from mythinking.board import MutableStateHolder
from mythinking.context import build_compact_agent_context

_MODEL_CALL_LIMIT = 10
_MAX_RETRIES = 2


def _context_injection_middleware(holder: MutableStateHolder) -> Any:
    @wrap_model_call
    def inject_project_context(request: Any, handler: Any) -> Any:
        base = request.system_prompt or ""
        block = build_compact_agent_context(holder.project_state)
        return handler(request.override(system_prompt=f"{base}\n\n{block}"))

    return inject_project_context


def build_thinker(
    model: Any,
    tools: list[BaseTool],
    system_prompt: str,
    holder: MutableStateHolder,
    *,
    checkpointer: Any | None = None,
    model_call_limit: int = _MODEL_CALL_LIMIT,
    max_retries: int = _MAX_RETRIES,
) -> Any:
    """Compile the Thinker agent for one turn (closes over `holder` for live context)."""
    return create_agent(
        model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[
            _context_injection_middleware(holder),
            ModelCallLimitMiddleware(run_limit=model_call_limit, exit_behavior="end"),
            ModelRetryMiddleware(max_retries=max_retries),
        ],
        checkpointer=checkpointer,
        name="thinker",
    )
