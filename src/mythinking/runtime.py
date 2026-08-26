"""Runtime orchestration for the runnable M1 supervisor loop."""

from collections.abc import Iterator
from pathlib import Path

from mythinking.agents.evidence_analyst import EvidenceAnalyst
from mythinking.agents.explorer import Explorer
from mythinking.agents.frame_analyst import FrameAnalyst
from mythinking.agents.planner import Planner
from mythinking.agents.researcher import Researcher
from mythinking.agents.supervisor import SupervisorAgent
from mythinking.agents.synthesizer import Synthesizer
from mythinking.branching import BranchSwitcher
from mythinking.config import Settings, get_settings
from mythinking.drift import DriftJudge
from mythinking.evidence import EvidenceLedger
from mythinking.graph import build_thinking_graph
from mythinking.llm import create_chat_model
from mythinking.persistence import StateRepository, open_sqlite_checkpointer
from mythinking.prompts import PromptRegistry
from mythinking.state import (
    AssistantTurn,
    ProjectState,
    SessionGraphState,
    TurnStreamEvent,
    TurnStreamEventType,
)


class ThinkingRuntime:
    """Own the persisted single-turn workflow used by the CLI."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        repository: StateRepository | None = None,
        checkpoint_database_path: Path | None = None,
        prompt_registry: PromptRegistry | None = None,
        frame_analyst: FrameAnalyst | None = None,
        supervisor: SupervisorAgent | None = None,
        drift_judge: DriftJudge | None = None,
        branch_switcher: BranchSwitcher | None = None,
        evidence_analyst: EvidenceAnalyst | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        explorer: Explorer | None = None,
        synthesizer: Synthesizer | None = None,
        researcher: Researcher | None = None,
        planner: Planner | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = repository or StateRepository(self.settings.state_database_path)
        self.checkpoint_database_path = (
            checkpoint_database_path or self.settings.checkpoint_database_path
        )
        self.prompt_registry = prompt_registry or PromptRegistry(self.settings.prompt_dir)
        self.frame_analyst = frame_analyst or FrameAnalyst(
            self.prompt_registry,
            create_chat_model(self.settings),
        )
        self.supervisor = supervisor or SupervisorAgent(
            self.prompt_registry,
            create_chat_model(self.settings),
        )
        self.drift_judge = drift_judge or DriftJudge(
            self.prompt_registry,
            create_chat_model(self.settings),
        )
        self.branch_switcher = branch_switcher or BranchSwitcher()
        self.evidence_analyst = evidence_analyst or EvidenceAnalyst(
            self.prompt_registry,
            create_chat_model(self.settings),
        )
        self.evidence_ledger = evidence_ledger or EvidenceLedger()
        self.explorer = explorer or Explorer(
            self.prompt_registry,
            create_chat_model(self.settings),
        )
        self.synthesizer = synthesizer or Synthesizer(
            self.prompt_registry,
            create_chat_model(self.settings),
        )
        self.researcher = researcher or Researcher(
            self.prompt_registry,
            create_chat_model(self.settings),
        )
        self.planner = planner or Planner(
            self.prompt_registry,
            create_chat_model(self.settings),
        )

    def run_turn(self, user_message: str, project_id: str | None = None) -> AssistantTurn:
        message = user_message.strip()
        if not message:
            raise ValueError("user_message must not be blank")

        project_state = self._load_project_state(project_id)
        graph_input = SessionGraphState(
            project_state=project_state,
            user_message=message,
        )

        with open_sqlite_checkpointer(self.checkpoint_database_path) as checkpointer:
            graph = build_thinking_graph(
                self.frame_analyst,
                self.supervisor,
                self.repository,
                drift_judge=self.drift_judge,
                branch_switcher=self.branch_switcher,
                evidence_analyst=self.evidence_analyst,
                evidence_ledger=self.evidence_ledger,
                explorer=self.explorer,
                synthesizer=self.synthesizer,
                researcher=self.researcher,
                planner=self.planner,
                checkpointer=checkpointer,
            )
            result = graph.invoke(
                graph_input,
                config={"configurable": {"thread_id": project_state.project_id}},
            )

        final_state = SessionGraphState.model_validate(result)
        if final_state.assistant_turn is None:
            raise RuntimeError("Graph completed without an assistant response")
        return final_state.assistant_turn

    def stream_turn(
        self, user_message: str, project_id: str | None = None
    ) -> Iterator[TurnStreamEvent]:
        """Stream one turn through the graph node by node, then the final turn.

        Validation (blank message, unknown `project_id`) happens eagerly, in
        this call, rather than lazily on first iteration -- so callers (e.g.
        `api.py`) can catch `ValueError`/`KeyError` and map them to an HTTP
        status before committing to a streaming response.
        """
        message = user_message.strip()
        if not message:
            raise ValueError("user_message must not be blank")
        project_state = self._load_project_state(project_id)
        return self._stream_graph(project_state, message)

    def _stream_graph(self, project_state: ProjectState, message: str) -> Iterator[TurnStreamEvent]:
        graph_input = SessionGraphState(
            project_state=project_state,
            user_message=message,
        )

        with open_sqlite_checkpointer(self.checkpoint_database_path) as checkpointer:
            graph = build_thinking_graph(
                self.frame_analyst,
                self.supervisor,
                self.repository,
                drift_judge=self.drift_judge,
                branch_switcher=self.branch_switcher,
                evidence_analyst=self.evidence_analyst,
                evidence_ledger=self.evidence_ledger,
                explorer=self.explorer,
                synthesizer=self.synthesizer,
                researcher=self.researcher,
                planner=self.planner,
                checkpointer=checkpointer,
            )
            final_turn: AssistantTurn | None = None
            for update in graph.stream(
                graph_input,
                config={"configurable": {"thread_id": project_state.project_id}},
                stream_mode="updates",
            ):
                for node_name, node_output in update.items():
                    mode = None
                    updated_state = (node_output or {}).get("project_state")
                    if isinstance(updated_state, ProjectState):
                        mode = updated_state.current_mode
                    turn_output = (node_output or {}).get("assistant_turn")
                    if isinstance(turn_output, AssistantTurn):
                        final_turn = turn_output
                    yield TurnStreamEvent(type=TurnStreamEventType.NODE, node=node_name, mode=mode)

            if final_turn is None:
                raise RuntimeError("Graph completed without an assistant response")
            yield TurnStreamEvent(type=TurnStreamEventType.TURN, turn=final_turn)

    def get_project_state(self, project_id: str) -> ProjectState | None:
        return self.repository.load(project_id)

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
