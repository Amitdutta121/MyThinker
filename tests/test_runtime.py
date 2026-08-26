from pathlib import Path

import pytest
from pydantic import SecretStr

from mythinking.branching import BranchSwitcher
from mythinking.config import Settings
from mythinking.evidence import EvidenceLedger
from mythinking.runtime import ThinkingRuntime, create_runtime
from mythinking.state import (
    AssistantTurn,
    BranchCommand,
    BranchStatus,
    DriftAssessment,
    DriftSignal,
    DriftStatus,
    EvidenceAnalysis,
    EvidenceDraft,
    EvidenceKind,
    FrameAnalysis,
    IdeaBranch,
    NorthStarUpdate,
    ProjectState,
    ThinkingMode,
)


class StubEvidenceAnalyst:
    """Deterministic stand-in that extracts no evidence unless configured to."""

    def __init__(self, analysis: EvidenceAnalysis | None = None) -> None:
        self.analysis = analysis or EvidenceAnalysis()
        self.calls: list[tuple[str, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> EvidenceAnalysis:
        self.calls.append((project_state.project_id, user_message))
        return self.analysis


class StubDriftJudge:
    """Deterministic stand-in that keeps ambiguous turns on track by default."""

    def __init__(self, resolved: DriftAssessment | None = None) -> None:
        self.resolved = resolved
        self.calls: list[tuple[ProjectState, str, DriftAssessment]] = []

    def resolve(
        self,
        project_state: ProjectState,
        user_message: str,
        assessment: DriftAssessment,
    ) -> DriftAssessment:
        self.calls.append((project_state, user_message, assessment))
        return self.resolved or DriftAssessment(
            status=DriftStatus.ON_TRACK,
            reason="stub judge default",
            signals=[DriftSignal.MODEL_FALLBACK],
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
            tuple[
                str,
                ThinkingMode,
                str,
                FrameAnalysis | None,
                DriftAssessment | None,
                BranchCommand | None,
            ]
        ] = []

    def respond(
        self,
        project_state: ProjectState,
        user_message: str,
        frame_analysis: FrameAnalysis | None = None,
        drift_assessment: DriftAssessment | None = None,
        branch_command: BranchCommand | None = None,
    ) -> AssistantTurn:
        self.calls.append(
            (
                project_state.project_id,
                project_state.current_mode,
                user_message,
                frame_analysis,
                drift_assessment,
                branch_command,
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
    drift_judge: StubDriftJudge | None = None,
    branch_switcher: BranchSwitcher | None = None,
    evidence_analyst: StubEvidenceAnalyst | None = None,
    evidence_ledger: EvidenceLedger | None = None,
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
        drift_judge=drift_judge or StubDriftJudge(),
        branch_switcher=branch_switcher or BranchSwitcher(),
        evidence_analyst=evidence_analyst or StubEvidenceAnalyst(),
        evidence_ledger=evidence_ledger or EvidenceLedger(),
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


def test_run_turn_resolves_ambiguous_drift_through_configured_judge(tmp_path: Path) -> None:
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
    resolved = DriftAssessment(
        status=DriftStatus.DRIFTED,
        tangent_summary="Focus on the riskiest part first",
        branch_name="Riskiest Part",
    )
    drift_judge = StubDriftJudge(resolved)
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
        drift_judge=drift_judge,
    )
    seed_turn = runtime.run_turn(
        "I need a better way to keep product idea notes focused for solo founders."
    )

    ambiguous_turn = runtime.run_turn(
        "Focus on the riskiest part first.",
        project_id=seed_turn.project_id,
    )
    saved = runtime.get_project_state(seed_turn.project_id)

    assert drift_judge.calls
    assert ambiguous_turn.mode is ThinkingMode.CHALLENGE
    assert saved is not None
    assert saved.branches
    assert saved.branches[0].summary == "Focus on the riskiest part first"


def test_run_turn_applies_an_explicit_branch_switch_command(tmp_path: Path) -> None:
    frame_analyst = SequenceFrameAnalyst(
        [
            FrameAnalysis(
                north_star=NorthStarUpdate(
                    problem_statement="Product idea notes keep drifting",
                    desired_outcome="Keep the main thread focused",
                    beneficiary="Solo founder",
                )
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

    project_state = runtime.get_project_state(seed_turn.project_id)
    assert project_state is not None
    project_state.branches.append(
        IdeaBranch(
            name="Newsletter Idea",
            summary="Start a newsletter for solo founders",
            status=BranchStatus.PARKED,
        )
    )
    runtime.repository.save(project_state)

    runtime.run_turn(
        "Let's switch to the newsletter branch.",
        project_id=seed_turn.project_id,
    )
    saved = runtime.get_project_state(seed_turn.project_id)

    assert saved is not None
    assert saved.active_branch_id == saved.branches[0].id
    assert saved.branches[0].status is BranchStatus.ACTIVE
    assert len(frame_analyst.calls) == 1
    switch_call = supervisor.calls[-1]
    assert switch_call[5] is not None
    assert switch_call[5].target_branch_name == "Newsletter Idea"


def test_run_turn_writes_extracted_evidence_into_project_state(tmp_path: Path) -> None:
    frame_analyst = SequenceFrameAnalyst(
        [
            FrameAnalysis(
                north_star=NorthStarUpdate(
                    problem_statement="Product idea notes keep drifting",
                    desired_outcome="Keep the main thread focused",
                    beneficiary="Solo founder",
                )
            ),
        ]
    )
    supervisor = RecordingSupervisor()
    evidence_analyst = StubEvidenceAnalyst(
        EvidenceAnalysis(
            evidence_to_add=[
                EvidenceDraft(
                    claim="Remote work always reduces innovation",
                    kind=EvidenceKind.HYPOTHESIS,
                )
            ]
        )
    )
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
        evidence_analyst=evidence_analyst,
    )

    turn = runtime.run_turn("Remote work always reduces innovation, so require office attendance.")
    saved = runtime.get_project_state(turn.project_id)

    assert evidence_analyst.calls
    assert saved is not None
    assert len(saved.evidence) == 1
    assert saved.evidence[0].kind is EvidenceKind.HYPOTHESIS
    assert saved.evidence[0].claim == "Remote work always reduces innovation"


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
