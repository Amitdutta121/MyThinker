"""Runtime for the single-agent Thinker loop.

Loads the project board, builds this turn's tool set + agent, runs the agentic
loop, derives a display mode, and persists. No LangGraph workflow, no intent
classifier, no drift pipeline -- tool selection is the model's own and tool
preconditions keep the board correct.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.store.sqlite import SqliteStore

from mythinking.agent import build_thinker
from mythinking.agents.evidence_analyst import EvidenceAnalyst
from mythinking.agents.explorer import Explorer
from mythinking.agents.frame_analyst import FrameAnalyst
from mythinking.agents.planner import Planner
from mythinking.agents.profile_extractor import ProfileExtractor
from mythinking.agents.synthesizer import Synthesizer
from mythinking.board import MutableStateHolder, derive_mode
from mythinking.config import Settings, get_settings
from mythinking.context import ContextRetriever
from mythinking.llm import create_chat_model, create_embeddings_model
from mythinking.persistence import ProfileRepository, StateRepository, open_sqlite_checkpointer
from mythinking.profile import ProfileService
from mythinking.prompts import PromptRegistry
from mythinking.retrieval import open_document_store
from mythinking.state import (
    AssistantTurn,
    ProjectState,
    TurnStreamEvent,
    TurnStreamEventType,
    UserProfile,
)
from mythinking.tools import ThinkingToolDeps, build_thinking_tools

_FALLBACK_MESSAGE = (
    "I need a bit more time to think this through -- could you ask again, "
    "maybe narrowed down a little?"
)
_SYSTEM_PROMPT_ID = "lead_partner"


class ThinkingRuntime:
    """Own the persisted single-turn Thinker workflow used by the CLI and API."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        repository: StateRepository | None = None,
        checkpoint_database_path: Path | None = None,
        prompt_registry: PromptRegistry | None = None,
        agent_model: Any | None = None,
        gate_model: Any | None = None,
        frame_analyst: FrameAnalyst | None = None,
        explorer: Explorer | None = None,
        synthesizer: Synthesizer | None = None,
        planner: Planner | None = None,
        evidence_analyst: EvidenceAnalyst | None = None,
        profile_extractor: ProfileExtractor | None = None,
        profile_repository: ProfileRepository | None = None,
        store: SqliteStore | None = None,
        context_retriever: ContextRetriever | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or StateRepository(self.settings.state_database_path)
        self.checkpoint_database_path = (
            checkpoint_database_path or self.settings.checkpoint_database_path
        )
        self.prompt_registry = prompt_registry or PromptRegistry(self.settings.prompt_dir)

        engines_supplied = all(
            x is not None for x in (frame_analyst, explorer, synthesizer, planner, evidence_analyst)
        )

        # A real SqliteStore backs research + document tools and the evidence
        # retriever. Opened here only when the caller did not supply one (and
        # did not supply a full set of engine doubles) so a fakes-only runtime
        # never needs an API key / embeddings client.
        self.store: SqliteStore | None = store
        if context_retriever is not None:
            self._context_retriever = context_retriever
            if self.store is None:
                self.store = context_retriever.store
        elif self.store is not None:
            self._context_retriever = ContextRetriever(
                self.store,
                threshold=self.settings.context_retrieval_threshold,
                top_k=self.settings.context_retrieval_top_k,
            )
        elif engines_supplied:
            self._context_retriever = None  # type: ignore[assignment]
        else:
            self._store_cm = open_document_store(
                self.settings.store_database_path,
                create_embeddings_model(self.settings),
                dimensions=self.settings.embedding_dimensions,
            )
            self.store = self._store_cm.__enter__()
            self._context_retriever = ContextRetriever(
                self.store,
                threshold=self.settings.context_retrieval_threshold,
                top_k=self.settings.context_retrieval_top_k,
            )

        self._agent_model = agent_model or create_chat_model(self.settings)
        gate = gate_model or create_chat_model(self.settings)

        def _model() -> Any:
            return create_chat_model(self.settings)

        self.deps = ThinkingToolDeps(
            frame_analyst=frame_analyst or FrameAnalyst(self.prompt_registry, _model()),
            explorer=explorer or Explorer(self.prompt_registry, _model()),
            synthesizer=synthesizer or Synthesizer(self.prompt_registry, _model()),
            planner=planner or Planner(self.prompt_registry, _model()),
            evidence_analyst=evidence_analyst or EvidenceAnalyst(self.prompt_registry, _model()),
            gate_model=gate,
        )

        self.profile_repository = profile_repository or ProfileRepository(
            self.settings.state_database_path
        )
        self._profile_service = ProfileService()
        self.profile_extractor = profile_extractor
        if self.profile_extractor is None and self.settings.enable_profile_extraction:
            self.profile_extractor = ProfileExtractor(self.prompt_registry, _model())

    # ------------------------------------------------------------------ public

    def run_turn(self, user_message: str, project_id: str | None = None) -> AssistantTurn:
        message = _require_message(user_message)
        holder = MutableStateHolder(project_state=self._load_project_state(project_id))
        result = self._invoke_agent(holder, message)
        final_text = _final_text(result)
        return self._finalize(holder, message, final_text)

    def stream_turn(
        self, user_message: str, project_id: str | None = None
    ) -> Iterator[TurnStreamEvent]:
        """Stream one turn: a NODE event per tool the agent runs, then a TURN event.

        Blank message / unknown project_id are raised eagerly here so `api.py` can
        map them to an HTTP status before the streaming response starts.
        """
        message = _require_message(user_message)
        holder = MutableStateHolder(project_state=self._load_project_state(project_id))
        return self._stream_agent(holder, message)

    def get_project_state(self, project_id: str) -> ProjectState | None:
        return self.repository.load(project_id)

    def get_user_profile(self) -> UserProfile:
        return self.profile_repository.load()

    # ----------------------------------------------------------------- internal

    def _build_tools(self, holder: MutableStateHolder, message: str) -> list[Any]:
        return build_thinking_tools(
            holder,
            message,
            deps=self.deps,
            context_retriever=self._context_retriever,
            store=self.store,
            settings=self.settings,
        )

    def _system_prompt(self) -> str:
        return self.prompt_registry.get(_SYSTEM_PROMPT_ID).render({})

    def _invoke_agent(self, holder: MutableStateHolder, message: str) -> dict[str, Any]:
        tools = self._build_tools(holder, message)
        with open_sqlite_checkpointer(self.checkpoint_database_path) as checkpointer:
            agent = build_thinker(
                self._agent_model,
                tools,
                self._system_prompt(),
                holder,
                checkpointer=checkpointer,
            )
            return agent.invoke(
                {"messages": [("user", message)]},
                config={"configurable": {"thread_id": holder.project_state.project_id}},
            )

    def _stream_agent(self, holder: MutableStateHolder, message: str) -> Iterator[TurnStreamEvent]:
        tools = self._build_tools(holder, message)
        final_text = ""
        with open_sqlite_checkpointer(self.checkpoint_database_path) as checkpointer:
            agent = build_thinker(
                self._agent_model,
                tools,
                self._system_prompt(),
                holder,
                checkpointer=checkpointer,
            )
            for update in agent.stream(
                {"messages": [("user", message)]},
                config={"configurable": {"thread_id": holder.project_state.project_id}},
                stream_mode="updates",
            ):
                for node_output in update.values():
                    for msg in (node_output or {}).get("messages", []) or []:
                        name = getattr(msg, "name", None)
                        if name:
                            yield TurnStreamEvent(type=TurnStreamEventType.NODE, node=name)
                        elif isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                            text = _message_text(msg)
                            if text:
                                final_text = text
        turn = self._finalize(holder, message, final_text)
        yield TurnStreamEvent(type=TurnStreamEventType.TURN, turn=turn)

    def _finalize(self, holder: MutableStateHolder, message: str, final_text: str) -> AssistantTurn:
        state = holder.project_state
        state.current_mode = derive_mode(state)
        state.mark_updated()
        self.repository.save(state)
        self._maybe_extract_profile(message)
        return AssistantTurn(
            project_id=state.project_id,
            mode=state.current_mode,
            message=final_text.strip() or _FALLBACK_MESSAGE,
            question="",
        )

    def _maybe_extract_profile(self, message: str) -> None:
        if self.profile_extractor is None:
            return
        profile = self.profile_repository.load()
        analysis = self.profile_extractor.analyze(profile, message)
        self.profile_repository.save(self._profile_service.merge(profile, analysis))

    def _load_project_state(self, project_id: str | None) -> ProjectState:
        if project_id is None:
            return ProjectState()
        project_state = self.repository.load(project_id)
        if project_state is None:
            raise KeyError(f"Unknown project_id: {project_id}")
        return project_state


def create_runtime(
    settings: Settings | None = None,
    *,
    state_database_path: Path | None = None,
    checkpoint_database_path: Path | None = None,
) -> ThinkingRuntime:
    runtime_settings = settings or get_settings()
    return ThinkingRuntime(
        runtime_settings,
        repository=StateRepository(state_database_path or runtime_settings.state_database_path),
        checkpoint_database_path=(
            checkpoint_database_path or runtime_settings.checkpoint_database_path
        ),
    )


def _require_message(user_message: str) -> str:
    message = user_message.strip()
    if not message:
        raise ValueError("user_message must not be blank")
    return message


def _final_text(result: dict[str, Any]) -> str:
    for message in reversed(result.get("messages", [])):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            text = _message_text(message)
            if text:
                return text
    return ""


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part if isinstance(part, str) else str(part.get("text", ""))
            for part in content
            if isinstance(part, str) or (isinstance(part, dict) and "text" in part)
        ]
        return "\n".join(parts)
    return str(content)
