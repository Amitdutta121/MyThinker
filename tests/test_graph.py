from pathlib import Path

from mythinking.graph import (
    apply_frame_analysis,
    build_thinking_graph,
    capture_node,
    choose_mode,
)
from mythinking.persistence import StateRepository
from mythinking.state import (
    AssistantTurn,
    AssumptionDraft,
    DriftAssessment,
    DriftStatus,
    FrameAnalysis,
    NorthStarUpdate,
    ProjectState,
    SessionGraphState,
    ThinkingMode,
)


class FakeFrameAnalyst:
    def __init__(self, analysis: FrameAnalysis) -> None:
        self.analysis = analysis
        self.calls: list[tuple[ProjectState, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> FrameAnalysis:
        self.calls.append((project_state, user_message))
        return self.analysis


class FakeSupervisor:
    def __init__(self) -> None:
        self.calls: list[
            tuple[ProjectState, str, FrameAnalysis | None, DriftAssessment | None]
        ] = []

    def respond(
        self,
        project_state: ProjectState,
        user_message: str,
        frame_analysis: FrameAnalysis | None = None,
        drift_assessment: DriftAssessment | None = None,
    ) -> AssistantTurn:
        self.calls.append((project_state, user_message, frame_analysis, drift_assessment))
        question = frame_analysis.recommended_question if frame_analysis else ""
        return AssistantTurn(
            project_id=project_state.project_id,
            mode=project_state.current_mode,
            message=f"{project_state.current_mode.value}:{user_message}",
            question=question,
        )


def test_capture_node_trims_user_message() -> None:
    state = SessionGraphState(project_state=ProjectState(), user_message="  sharpen this idea  ")

    result = capture_node(state)

    assert result == {"user_message": "sharpen this idea"}


def test_choose_mode_returns_capture_when_core_frame_is_present() -> None:
    project_state = ProjectState()
    project_state.north_star.problem_statement = "Manual planning is fragmented"
    project_state.north_star.desired_outcome = "A reusable thought process"
    project_state.north_star.beneficiary = "Solo founder"

    mode = choose_mode(project_state, FrameAnalysis(), None)

    assert mode is ThinkingMode.CAPTURE


def test_choose_mode_returns_challenge_when_drift_is_detected() -> None:
    project_state = ProjectState()

    mode = choose_mode(
        project_state,
        FrameAnalysis(),
        DriftAssessment(status=DriftStatus.DRIFTED),
    )

    assert mode is ThinkingMode.CHALLENGE


def test_apply_frame_analysis_merges_and_deduplicates_updates() -> None:
    project_state = ProjectState()
    project_state.north_star.constraints = ["Keep it local"]
    project_state.north_star.success_criteria = ["Save progress"]
    project_state.north_star.non_goals = ["Live browsing"]
    project_state.open_questions = ["Who is this for?"]
    project_state.assumptions = []

    frame_analysis = FrameAnalysis(
        north_star=NorthStarUpdate(
            title="  Better planning  ",
            problem_statement="  Scattered notes hide the real problem  ",
            desired_outcome="  Reach a next step quickly  ",
            beneficiary="  Product teams  ",
            constraints_to_add=["Keep it local", "Offline-first"],
            success_criteria_to_add=["Save progress", "Produce a next action"],
            non_goals_to_add=["Live browsing", "Long-term memory"],
            current_hypothesis="  A guided loop will reduce drift  ",
            next_action="  Test a capture flow  ",
        ),
        assumptions_to_add=[
            AssumptionDraft(statement="Users need structure", importance=5),
            AssumptionDraft(statement="  users need structure  ", importance=2),
        ],
        open_questions_to_add=["Who is this for?", "What is the first workflow?"],
        recommended_question="  What outcome matters most right now?  ",
    )

    updated = apply_frame_analysis(project_state, frame_analysis)

    assert updated.north_star.title == "Better planning"
    assert updated.north_star.problem_statement == "Scattered notes hide the real problem"
    assert updated.north_star.desired_outcome == "Reach a next step quickly"
    assert updated.north_star.beneficiary == "Product teams"
    assert updated.north_star.current_hypothesis == "A guided loop will reduce drift"
    assert updated.north_star.next_action == "Test a capture flow"
    assert updated.north_star.constraints == ["Keep it local", "Offline-first"]
    assert updated.north_star.success_criteria == ["Save progress", "Produce a next action"]
    assert updated.north_star.non_goals == ["Live browsing", "Long-term memory"]
    assert [item.statement for item in updated.assumptions] == ["Users need structure"]
    assert updated.open_questions == [
        "Who is this for?",
        "What is the first workflow?",
        "What outcome matters most right now?",
    ]


def test_build_thinking_graph_runs_capture_flow_and_persists_state(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    analysis = FrameAnalysis(
        north_star=NorthStarUpdate(
            problem_statement="Manual thinking is inconsistent",
            desired_outcome="Capture ideas into a reusable frame",
            beneficiary="Indie maker",
        )
    )
    frame_analyst = FakeFrameAnalyst(analysis)
    supervisor = FakeSupervisor()
    graph = build_thinking_graph(frame_analyst, supervisor, repository)

    initial_state = SessionGraphState(
        project_state=ProjectState(),
        user_message="  I want a better way to think through product ideas  ",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))
    saved = repository.load(result.project_state.project_id)

    assert result.project_state.current_mode is ThinkingMode.CAPTURE
    assert result.assistant_turn is not None
    assert result.assistant_turn.mode is ThinkingMode.CAPTURE
    assert result.assistant_turn.message == (
        "capture:I want a better way to think through product ideas"
    )
    assert frame_analyst.calls[0][1] == "I want a better way to think through product ideas"
    assert supervisor.calls[0][0].current_mode is ThinkingMode.CAPTURE
    assert supervisor.calls[0][3] is not None
    assert saved is not None
    assert saved.current_mode is ThinkingMode.CAPTURE
    assert saved.north_star.problem_statement == "Manual thinking is inconsistent"


def test_build_thinking_graph_runs_clarify_flow_when_question_is_needed(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    analysis = FrameAnalysis(
        north_star=NorthStarUpdate(problem_statement="Need a clearer target"),
        recommended_question="What specific decision are you trying to make?",
    )
    frame_analyst = FakeFrameAnalyst(analysis)
    supervisor = FakeSupervisor()
    graph = build_thinking_graph(frame_analyst, supervisor, repository)

    initial_state = SessionGraphState(
        project_state=ProjectState(),
        user_message="Help me think this through",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.project_state.current_mode is ThinkingMode.CLARIFY
    assert result.assistant_turn is not None
    assert result.assistant_turn.mode is ThinkingMode.CLARIFY
    assert result.assistant_turn.question == "What specific decision are you trying to make?"


def test_build_thinking_graph_preserves_detected_tangent_as_branch(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    graph = build_thinking_graph(frame_analyst, supervisor, repository)
    project_state = ProjectState()
    project_state.north_star.problem_statement = "Product idea notes are scattered"
    project_state.north_star.desired_outcome = "Keep the idea thread focused"
    project_state.north_star.beneficiary = "Solo founder"

    initial_state = SessionGraphState(
        project_state=project_state,
        user_message="Tell me everything about vector databases.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.project_state.current_mode is ThinkingMode.CHALLENGE
    assert result.drift_assessment is not None
    assert result.drift_assessment.status is DriftStatus.DRIFTED
    assert result.project_state.branches
    assert result.project_state.branches[0].summary == "Tell me everything about vector databases"
    assert result.project_state.branches[0].status.value == "parked"


def test_build_thinking_graph_does_not_merge_tangent_frame_updates_into_north_star(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    analysis = FrameAnalysis(
        north_star=NorthStarUpdate(current_hypothesis="Use vector databases for retrieval"),
        open_questions_to_add=["Which vector database should I use?"],
        recommended_question="Which vector database should I use?",
    )
    frame_analyst = FakeFrameAnalyst(analysis)
    supervisor = FakeSupervisor()
    graph = build_thinking_graph(frame_analyst, supervisor, repository)
    project_state = ProjectState()
    project_state.north_star.problem_statement = "Product idea notes are scattered"
    project_state.north_star.desired_outcome = "Keep the idea thread focused"
    project_state.north_star.beneficiary = "Solo founder"

    initial_state = SessionGraphState(
        project_state=project_state,
        user_message="Tell me everything about vector databases.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.drift_assessment is not None
    assert result.drift_assessment.status is DriftStatus.DRIFTED
    assert result.project_state.north_star.current_hypothesis == ""
    assert result.project_state.open_questions == []
    assert result.project_state.branches
    assert result.project_state.branches[0].summary == "Tell me everything about vector databases"
