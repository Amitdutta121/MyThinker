"""LangGraph workflow for the runnable core loop plus M2a drift control."""

from collections.abc import Iterable
from typing import Any

from langgraph.graph import END, START, StateGraph

from mythinking.agents.frame_analyst import FrameAnalyst
from mythinking.agents.supervisor import SupervisorAgent
from mythinking.branching import BranchManager
from mythinking.drift import DriftDetector
from mythinking.persistence import StateRepository
from mythinking.state import (
    Assumption,
    DriftAssessment,
    DriftStatus,
    FrameAnalysis,
    ProjectState,
    SessionGraphState,
    ThinkingMode,
)


def build_thinking_graph(
    frame_analyst: FrameAnalyst,
    supervisor: SupervisorAgent,
    repository: StateRepository,
    *,
    drift_detector: DriftDetector | None = None,
    branch_manager: BranchManager | None = None,
    checkpointer: Any = None,
):
    workflow = StateGraph(SessionGraphState)
    drift_detector = drift_detector or DriftDetector()
    branch_manager = branch_manager or BranchManager()

    workflow.add_node("capture", capture_node)
    workflow.add_node("frame", _frame_node(frame_analyst))
    workflow.add_node("detect_drift", _drift_node(drift_detector, branch_manager))
    workflow.add_node("choose_mode", choose_mode_node)
    workflow.add_node("respond", _respond_node(supervisor))
    workflow.add_node("persist", _persist_node(repository))

    workflow.add_edge(START, "capture")
    workflow.add_edge("capture", "frame")
    workflow.add_edge("frame", "detect_drift")
    workflow.add_edge("detect_drift", "choose_mode")
    workflow.add_edge("choose_mode", "respond")
    workflow.add_edge("respond", "persist")
    workflow.add_edge("persist", END)

    return workflow.compile(checkpointer=checkpointer)


def capture_node(state: SessionGraphState) -> dict[str, str]:
    message = state.user_message.strip()
    if not message:
        raise ValueError("user_message must not be blank")
    return {"user_message": message}


def _frame_node(frame_analyst: FrameAnalyst):
    def run(state: SessionGraphState) -> dict[str, FrameAnalysis]:
        analysis = frame_analyst.analyze(state.project_state, state.user_message)
        return {
            "frame_analysis": analysis,
        }

    return run


def choose_mode_node(state: SessionGraphState) -> dict[str, ProjectState]:
    project_state = state.project_state.model_copy(deep=True)
    project_state.current_mode = choose_mode(
        project_state,
        state.frame_analysis,
        state.drift_assessment,
    )
    return {"project_state": project_state}


def _respond_node(supervisor: SupervisorAgent):
    def run(state: SessionGraphState) -> dict[str, Any]:
        assistant_turn = supervisor.respond(
            state.project_state,
            state.user_message,
            state.frame_analysis,
            state.drift_assessment,
        )
        return {"assistant_turn": assistant_turn}

    return run


def _persist_node(repository: StateRepository):
    def run(state: SessionGraphState) -> dict[str, ProjectState]:
        repository.save(state.project_state)
        return {"project_state": state.project_state}

    return run


def _drift_node(
    drift_detector: DriftDetector,
    branch_manager: BranchManager,
):
    def run(state: SessionGraphState) -> dict[str, DriftAssessment | ProjectState]:
        assessment = drift_detector.assess(state.project_state, state.user_message)
        if assessment.status is DriftStatus.DRIFTED:
            project_state = branch_manager.preserve_tangent(state.project_state, assessment)
        elif state.frame_analysis is not None:
            project_state = apply_frame_analysis(state.project_state, state.frame_analysis)
        else:
            project_state = state.project_state.model_copy(deep=True)
        return {
            "drift_assessment": assessment,
            "project_state": project_state,
        }

    return run


def choose_mode(
    project_state: ProjectState,
    frame_analysis: FrameAnalysis | None = None,
    drift_assessment: DriftAssessment | None = None,
) -> ThinkingMode:
    if drift_assessment and drift_assessment.status is DriftStatus.DRIFTED:
        return ThinkingMode.CHALLENGE

    north_star = project_state.north_star
    missing_core_frame = any(
        not field.strip()
        for field in (
            north_star.problem_statement,
            north_star.desired_outcome,
            north_star.beneficiary,
        )
    )
    has_follow_up_question = bool(frame_analysis and frame_analysis.recommended_question.strip())
    if missing_core_frame or has_follow_up_question:
        return ThinkingMode.CLARIFY
    return ThinkingMode.CAPTURE


def apply_frame_analysis(
    project_state: ProjectState,
    frame_analysis: FrameAnalysis,
) -> ProjectState:
    project = project_state.model_copy(deep=True)
    north_star_update = frame_analysis.north_star

    if north_star_update.title is not None:
        project.north_star.title = north_star_update.title.strip()
    if north_star_update.problem_statement is not None:
        project.north_star.problem_statement = north_star_update.problem_statement.strip()
    if north_star_update.desired_outcome is not None:
        project.north_star.desired_outcome = north_star_update.desired_outcome.strip()
    if north_star_update.beneficiary is not None:
        project.north_star.beneficiary = north_star_update.beneficiary.strip()
    if north_star_update.current_hypothesis is not None:
        project.north_star.current_hypothesis = north_star_update.current_hypothesis.strip()
    if north_star_update.next_action is not None:
        project.north_star.next_action = north_star_update.next_action.strip()

    project.north_star.constraints = _append_unique(
        project.north_star.constraints,
        north_star_update.constraints_to_add,
    )
    project.north_star.success_criteria = _append_unique(
        project.north_star.success_criteria,
        north_star_update.success_criteria_to_add,
    )
    project.north_star.non_goals = _append_unique(
        project.north_star.non_goals,
        north_star_update.non_goals_to_add,
    )

    existing_assumptions = {_normalize(item.statement) for item in project.assumptions}
    for draft in frame_analysis.assumptions_to_add:
        key = _normalize(draft.statement)
        if key and key not in existing_assumptions:
            project.assumptions.append(
                Assumption(statement=draft.statement.strip(), importance=draft.importance)
            )
            existing_assumptions.add(key)

    project.open_questions = _append_unique(
        project.open_questions,
        frame_analysis.open_questions_to_add,
    )
    if frame_analysis.recommended_question.strip():
        project.open_questions = _append_unique(
            project.open_questions,
            [frame_analysis.recommended_question],
        )
    return project


def _append_unique(existing: list[str], additions: Iterable[str]) -> list[str]:
    merged = list(existing)
    seen = {_normalize(item) for item in merged}
    for item in additions:
        cleaned = item.strip()
        key = _normalize(cleaned)
        if cleaned and key not in seen:
            merged.append(cleaned)
            seen.add(key)
    return merged


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
