from pathlib import Path

import pytest
from pydantic import SecretStr

from mythinking.config import Settings
from mythinking.runtime import ThinkingRuntime, create_runtime
from mythinking.state import (
    AssistantTurn,
    DriftAssessment,
    FrameAnalysis,
    NorthStarUpdate,
    ProjectState,
    ThinkingMode,
)


class SequenceFrameAnalyst:
    def __init__(self, analyses: list[FrameAnalysis]) -> None:
        self.analyses = analyses
        self.calls: list[tuple[str, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> FrameAnalysis:
        self.calls.append((project_state.project_id, user_message))
        return self.analyses[len(self.calls) - 1]


class RecordingSupervisor:
    def __init__(self) -> None:
        self.calls: list[
            tuple[str, ThinkingMode, str, FrameAnalysis | None, DriftAssessment | None]
        ] = []

    def respond(
        self,
        project_state: ProjectState,
        user_message: str,
        frame_analysis: FrameAnalysis | None = None,
        drift_assessment: DriftAssessment | None = None,
    ) -> AssistantTurn:
        self.calls.append(
            (
                project_state.project_id,
                project_state.current_mode,
                user_message,
                frame_analysis,
                drift_assessment,
            )
        )
        question = frame_analysis.recommended_question if frame_analysis else ""
        return AssistantTurn(
            project_id=project_state.project_id,
            mode=project_state.current_mode,
            message=f"{project_state.current_mode.value}:{user_message}",
            question=question,
        )


def _build_runtime(
    tmp_path: Path,
    *,
    frame_analyst: SequenceFrameAnalyst,
    supervisor: RecordingSupervisor,
) -> ThinkingRuntime:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        prompt_dir=tmp_path / "prompts",
    )
    return ThinkingRuntime(
        settings=settings,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
    )


def test_run_turn_capture_flow_persists_new_project(tmp_path: Path) -> None:
    frame_analyst = SequenceFrameAnalyst(
        [
            FrameAnalysis(
                north_star=NorthStarUpdate(
                    problem_statement="Notes are scattered",
                    desired_outcome="Capture a coherent frame",
                    beneficiary="Founder",
                )
            )
        ]
    )
    supervisor = RecordingSupervisor()
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
    )

    turn = runtime.run_turn("  Help me structure this product idea  ")
    saved = runtime.get_project_state(turn.project_id)

    assert turn.mode is ThinkingMode.CAPTURE
    assert turn.message == "capture:Help me structure this product idea"
    assert saved is not None
    assert saved.project_id == turn.project_id
    assert saved.current_mode is ThinkingMode.CAPTURE
    assert saved.north_star.problem_statement == "Notes are scattered"
    assert frame_analyst.calls == [(turn.project_id, "Help me structure this product idea")]
    assert supervisor.calls[0][1] is ThinkingMode.CAPTURE
    assert supervisor.calls[0][4] is not None


def test_run_turn_resumes_existing_project_and_persists_clarify_updates(
    tmp_path: Path,
) -> None:
    frame_analyst = SequenceFrameAnalyst(
        [
            FrameAnalysis(
                north_star=NorthStarUpdate(
                    problem_statement="Need to decide launch scope",
                    desired_outcome="Capture the initial frame",
                    beneficiary="Small team",
                )
            ),
            FrameAnalysis(
                north_star=NorthStarUpdate(current_hypothesis="A narrower beta is safer"),
                recommended_question="Which users must the beta serve first?",
            ),
        ]
    )
    supervisor = RecordingSupervisor()
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
    )

    first_turn = runtime.run_turn("Map the launch decision")
    second_turn = runtime.run_turn("Focus on the riskiest part", project_id=first_turn.project_id)
    saved = runtime.get_project_state(first_turn.project_id)

    assert second_turn.project_id == first_turn.project_id
    assert second_turn.mode is ThinkingMode.CLARIFY
    assert second_turn.question == "Which users must the beta serve first?"
    assert saved is not None
    assert saved.current_mode is ThinkingMode.CLARIFY
    assert saved.north_star.current_hypothesis == "A narrower beta is safer"
    assert saved.open_questions == ["Which users must the beta serve first?"]
    assert frame_analyst.calls == [
        (first_turn.project_id, "Map the launch decision"),
        (first_turn.project_id, "Focus on the riskiest part"),
    ]
    assert [call[1] for call in supervisor.calls] == [
        ThinkingMode.CAPTURE,
        ThinkingMode.CLARIFY,
    ]


def test_run_turn_preserves_tangent_branch_and_sets_challenge_mode(tmp_path: Path) -> None:
    frame_analyst = SequenceFrameAnalyst(
        [
            FrameAnalysis(
                north_star=NorthStarUpdate(
                    problem_statement="Product idea notes keep drifting",
                    desired_outcome="Keep the main thread focused",
                    beneficiary="Solo founder",
                )
            ),
            FrameAnalysis(),
        ]
    )
    supervisor = RecordingSupervisor()
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
    )
    seed_turn = runtime.run_turn(
        "I need a better way to keep product idea notes focused for solo founders."
    )

    drift_turn = runtime.run_turn(
        "Tell me everything about vector databases.",
        project_id=seed_turn.project_id,
    )
    saved = runtime.get_project_state(seed_turn.project_id)

    assert drift_turn.mode is ThinkingMode.CHALLENGE
    assert saved is not None
    assert saved.current_mode is ThinkingMode.CHALLENGE
    assert len(saved.branches) == 1
    assert saved.branches[0].summary == "Tell me everything about vector databases"


def test_run_turn_does_not_persist_tangent_frame_updates_into_core_state(tmp_path: Path) -> None:
    frame_analyst = SequenceFrameAnalyst(
        [
            FrameAnalysis(
                north_star=NorthStarUpdate(
                    problem_statement="Product idea notes keep drifting",
                    desired_outcome="Keep the main thread focused",
                    beneficiary="Solo founder",
                )
            ),
            FrameAnalysis(
                north_star=NorthStarUpdate(current_hypothesis="Use vector databases for retrieval"),
                open_questions_to_add=["Which vector database should I use?"],
                recommended_question="Which vector database should I use?",
            ),
        ]
    )
    supervisor = RecordingSupervisor()
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
    )
    seed_turn = runtime.run_turn(
        "I need a better way to keep product idea notes focused for solo founders."
    )

    runtime.run_turn(
        "Tell me everything about vector databases.",
        project_id=seed_turn.project_id,
    )
    saved = runtime.get_project_state(seed_turn.project_id)

    assert saved is not None
    assert saved.current_mode is ThinkingMode.CHALLENGE
    assert saved.north_star.current_hypothesis == ""
    assert saved.open_questions == []
    assert len(saved.branches) == 1
    assert saved.branches[0].summary == "Tell me everything about vector databases"


def test_get_project_state_returns_none_for_unknown_project(tmp_path: Path) -> None:
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=SequenceFrameAnalyst([FrameAnalysis()]),
        supervisor=RecordingSupervisor(),
    )

    assert runtime.get_project_state("missing") is None


def test_run_turn_rejects_unknown_project_id(tmp_path: Path) -> None:
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=SequenceFrameAnalyst([FrameAnalysis()]),
        supervisor=RecordingSupervisor(),
    )

    with pytest.raises(KeyError, match="Unknown project_id"):
        runtime.run_turn("resume this", project_id="missing")


def test_create_runtime_honors_explicit_database_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mythinking.runtime.create_chat_model", lambda settings: object())
    settings = Settings(
        _env_file=None,
        openrouter_api_key=SecretStr("test-key"),
        data_dir=tmp_path / "default-data",
        prompt_dir=tmp_path / "prompts",
    )
    state_database_path = tmp_path / "custom" / "state.db"
    checkpoint_database_path = tmp_path / "custom" / "checkpoints.db"

    runtime = create_runtime(
        settings=settings,
        state_database_path=state_database_path,
        checkpoint_database_path=checkpoint_database_path,
    )

    assert runtime.repository.database_path == state_database_path
    assert runtime.checkpoint_database_path == checkpoint_database_path
