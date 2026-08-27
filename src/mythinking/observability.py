"""Optional MLflow tracing for the Thinker agent.

Off by default. Set `MYTHINKING_MLFLOW_TRACING=true` (and install the
`observability` dependency group) to capture every turn -- the `build_thinker`
loop, each tool call, and every sub-agent LLM call -- as a nested MLflow trace.
`mlflow.langchain.autolog()` instruments LangChain *and* LangGraph, so no call
sites in `runtime.py` need to change.

View the traces with:

    uv run --group observability mlflow ui --backend-store-uri sqlite:///mlflow.db
"""

from __future__ import annotations

from mythinking.config import Settings, get_settings

_configured = False


def configure_tracing(settings: Settings | None = None) -> bool:
    """Enable MLflow autologging once per process. Returns True if tracing is on.

    A missing `mlflow` install (the group was not synced) is reported and
    swallowed rather than crashing the CLI/API -- tracing is a dev aid, not a
    hard requirement.
    """

    global _configured
    runtime = settings or get_settings()
    if not runtime.mlflow_tracing or _configured:
        return _configured

    try:
        import mlflow
    except ModuleNotFoundError:
        print(
            "MYTHINKING_MLFLOW_TRACING is set but mlflow is not installed; "
            "run `uv sync --group observability`. Continuing without tracing.",
        )
        return False

    mlflow.set_tracking_uri(runtime.mlflow_tracking_uri)
    mlflow.set_experiment(runtime.mlflow_experiment)
    mlflow.langchain.autolog()
    _configured = True
    print(
        f"MLflow tracing on -> experiment '{runtime.mlflow_experiment}' "
        f"at {runtime.mlflow_tracking_uri}",
    )
    return True
