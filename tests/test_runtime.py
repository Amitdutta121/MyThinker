from pathlib import Path

import pytest
from pydantic import SecretStr

from mythinking.agents.profile_extractor import ProfileExtractor
from mythinking.branching import BranchSwitcher
from mythinking.config import Settings
from mythinking.evidence import EvidenceLedger
from mythinking.runtime import ThinkingRuntime, create_runtime
from mythinking.state import (
    AlternativeDraft,
    AssistantTurn,
    BranchCommand,
    BranchStatus,
    ConvergenceOption,
    DriftAssessment,
    DriftSignal,
    DriftStatus,
    EvidenceAnalysis,
    EvidenceDraft,
    EvidenceKind,
    ExplorerAnalysis,
    FrameAnalysis,
    IdeaBranch,
    IntentClassification,
    NextActionDraft,
    NorthStarUpdate,
    PlannerAnalysis,
    ProfileAnalysis,
    ProjectState,
    ResearcherAnalysis,
    ResearchTask,
    ResearchTaskStatus,
    SynthesizerAnalysis,
    ThinkingMode,
    TurnIntent,
    TurnStreamEventType,
    UserProfile,
    UserProfileUpdate,
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


class StubIntentClassifier:
    """Deterministic stand-in classifying turns from a fixed sequence, repeating the last value."""

    def __init__(self, intents: list[TurnIntent] | None = None) -> None:
        self.intents = intents or [TurnIntent.NONE]
        self.calls: list[str] = []

    def classify(self, user_message: str) -> IntentClassification:
        self.calls.append(user_message)
        index = min(len(self.calls) - 1, len(self.intents) - 1)
        return IntentClassification(intent=self.intents[index])


class SequenceFrameAnalyst:
    def __init__(self, analyses: list[FrameAnalysis]) -> None:
        self.analyses = analyses
        self.calls: list[tuple[str, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> FrameAnalysis:
        self.calls.append((project_state.project_id, user_message))
        return self.analyses[len(self.calls) - 1]


class StubExplorer:
    """Deterministic stand-in that proposes no alternatives unless configured to."""

    def __init__(self, analysis: ExplorerAnalysis | None = None) -> None:
        self.analysis = analysis or ExplorerAnalysis()
        self.calls: list[tuple[str, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> ExplorerAnalysis:
        self.calls.append((project_state.project_id, user_message))
        return self.analysis


class StubSynthesizer:
    """Deterministic stand-in that converges nothing unless configured to."""

    def __init__(self, analysis: SynthesizerAnalysis | None = None) -> None:
        self.analysis = analysis or SynthesizerAnalysis()
        self.calls: list[tuple[str, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> SynthesizerAnalysis:
        self.calls.append((project_state.project_id, user_message))
        return self.analysis


class StubResearcher:
    """Deterministic stand-in that finds no evidence unless configured to."""

    def __init__(self, analysis: ResearcherAnalysis | None = None) -> None:
        self.analysis = analysis or ResearcherAnalysis()
        self.calls: list[tuple[str, str]] = []

    def analyze(
        self,
        project_state: ProjectState,
        user_message: str,
        research_task: ResearchTask | None = None,
    ) -> ResearcherAnalysis:
        self.calls.append((project_state.project_id, user_message))
        return self.analysis


class StubPlanner:
    """Deterministic stand-in that proposes no next actions unless configured to."""

    def __init__(self, analysis: PlannerAnalysis | None = None) -> None:
        self.analysis = analysis or PlannerAnalysis()
        self.calls: list[tuple[str, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> PlannerAnalysis:
        self.calls.append((project_state.project_id, user_message))
        return self.analysis


class StubProfileExtractor:
    """Deterministic stand-in that proposes no profile update unless configured to."""

    def __init__(self, analysis: ProfileAnalysis | None = None) -> None:
        self.analysis = analysis or ProfileAnalysis()
        self.calls: list[tuple[str, str]] = []

    def analyze(self, user_profile: UserProfile, user_message: str) -> ProfileAnalysis:
        self.calls.append((user_profile.role, user_message))
        return self.analysis


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
                ExplorerAnalysis | None,
                SynthesizerAnalysis | None,
                ResearcherAnalysis | None,
                PlannerAnalysis | None,
            ]
        ] = []

    def respond(
        self,
        project_state: ProjectState,
        user_message: str,
        frame_analysis: FrameAnalysis | None = None,
        drift_assessment: DriftAssessment | None = None,
        branch_command: BranchCommand | None = None,
        exploration_analysis: ExplorerAnalysis | None = None,
        synthesis: SynthesizerAnalysis | None = None,
        research_analysis: ResearcherAnalysis | None = None,
        planner_analysis: PlannerAnalysis | None = None,
    ) -> AssistantTurn:
        self.calls.append(
            (
                project_state.project_id,
                project_state.current_mode,
                user_message,
                frame_analysis,
                drift_assessment,
                branch_command,
                exploration_analysis,
                synthesis,
                research_analysis,
                planner_analysis,
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
    intent_classifier: StubIntentClassifier | None = None,
    drift_judge: StubDriftJudge | None = None,
    branch_switcher: BranchSwitcher | None = None,
    evidence_analyst: StubEvidenceAnalyst | None = None,
    evidence_ledger: EvidenceLedger | None = None,
    explorer: StubExplorer | None = None,
    synthesizer: StubSynthesizer | None = None,
    researcher: StubResearcher | None = None,
    planner: StubPlanner | None = None,
    profile_extractor: StubProfileExtractor | None = None,
    enable_profile_extraction: bool = False,
) -> ThinkingRuntime:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        prompt_dir=tmp_path / "prompts",
        enable_profile_extraction=enable_profile_extraction,
    )
    return ThinkingRuntime(
        settings=settings,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
        intent_classifier=intent_classifier or StubIntentClassifier(),
        drift_judge=drift_judge or StubDriftJudge(),
        branch_switcher=branch_switcher or BranchSwitcher(),
        evidence_analyst=evidence_analyst or StubEvidenceAnalyst(),
        evidence_ledger=evidence_ledger or EvidenceLedger(),
        explorer=explorer or StubExplorer(),
        synthesizer=synthesizer or StubSynthesizer(),
        researcher=researcher or StubResearcher(),
        planner=planner or StubPlanner(),
        profile_extractor=profile_extractor,
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


def test_run_turn_generates_alternatives_on_explicit_explore_request(tmp_path: Path) -> None:
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
    explorer = StubExplorer(
        ExplorerAnalysis(
            alternatives_to_add=[
                AlternativeDraft(name="Newsletter", summary="Start a weekly newsletter"),
            ]
        )
    )
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
        intent_classifier=StubIntentClassifier([TurnIntent.NONE, TurnIntent.EXPLORE]),
        explorer=explorer,
    )
    seed_turn = runtime.run_turn(
        "I need a better way to keep product idea notes focused for solo founders."
    )

    turn = runtime.run_turn(
        "Give me some alternatives for this.",
        project_id=seed_turn.project_id,
    )
    saved = runtime.get_project_state(seed_turn.project_id)

    assert explorer.calls
    assert turn.mode is ThinkingMode.EXPLORE
    assert saved is not None
    assert len(frame_analyst.calls) == 1
    assert [branch.name for branch in saved.branches] == ["Newsletter"]


def test_run_turn_converges_alternatives_on_explicit_converge_request(tmp_path: Path) -> None:
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
    synthesizer = StubSynthesizer(
        SynthesizerAnalysis(
            options_considered=[ConvergenceOption(branch_name="Newsletter Idea")],
            recommended_choice="Start with the newsletter",
        )
    )
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
        intent_classifier=StubIntentClassifier([TurnIntent.NONE, TurnIntent.CONVERGE]),
        synthesizer=synthesizer,
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
            status=BranchStatus.ACTIVE,
        )
    )
    runtime.repository.save(project_state)

    turn = runtime.run_turn(
        "Help me decide between these options.",
        project_id=seed_turn.project_id,
    )
    saved = runtime.get_project_state(seed_turn.project_id)

    assert synthesizer.calls
    assert turn.mode is ThinkingMode.CONVERGE
    assert saved is not None
    assert saved.branches[0].status is BranchStatus.MERGED
    assert saved.north_star.current_hypothesis == "Start with the newsletter"


def test_run_turn_answers_scoped_research_request_and_resolves_task(tmp_path: Path) -> None:
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
    researcher = StubResearcher(
        ResearcherAnalysis(
            findings_to_add=[
                EvidenceDraft(
                    claim="The changelog shows weekly releases",
                    kind=EvidenceKind.FACT,
                    source_title="Internal changelog",
                )
            ],
            task_resolved=True,
        )
    )
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
        intent_classifier=StubIntentClassifier([TurnIntent.NONE, TurnIntent.RESEARCH]),
        researcher=researcher,
    )
    seed_turn = runtime.run_turn(
        "I need a better way to keep product idea notes focused for solo founders."
    )

    project_state = runtime.get_project_state(seed_turn.project_id)
    assert project_state is not None
    task = ResearchTask(question="Do we ship weekly?")
    project_state.research_tasks.append(task)
    runtime.repository.save(project_state)

    turn = runtime.run_turn(
        "Can you research whether we ship weekly?",
        project_id=seed_turn.project_id,
    )
    saved = runtime.get_project_state(seed_turn.project_id)

    assert researcher.calls
    assert turn.mode is ThinkingMode.RESEARCH
    assert saved is not None
    assert len(frame_analyst.calls) == 1
    assert len(saved.evidence) == 1
    assert saved.research_tasks[0].status is ResearchTaskStatus.ANSWERED


def test_run_turn_plans_a_next_action_on_explicit_planning_request(tmp_path: Path) -> None:
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
    planner = StubPlanner(
        PlannerAnalysis(
            next_actions_to_add=[
                NextActionDraft(description="Draft the first newsletter issue", time_box_minutes=30)
            ]
        )
    )
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
        intent_classifier=StubIntentClassifier([TurnIntent.NONE, TurnIntent.PLAN]),
        planner=planner,
    )
    seed_turn = runtime.run_turn(
        "I need a better way to keep product idea notes focused for solo founders."
    )

    turn = runtime.run_turn(
        "What should I do next?",
        project_id=seed_turn.project_id,
    )
    saved = runtime.get_project_state(seed_turn.project_id)

    assert planner.calls
    assert turn.mode is ThinkingMode.DECIDE
    assert saved is not None
    assert len(frame_analyst.calls) == 1
    assert [action.description for action in saved.next_actions] == [
        "Draft the first newsletter issue"
    ]


def test_run_turn_extracts_and_persists_profile_when_an_extractor_is_wired(
    tmp_path: Path,
) -> None:
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
    profile_extractor = StubProfileExtractor(
        ProfileAnalysis(profile_update=UserProfileUpdate(role="Backend engineer"))
    )
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=frame_analyst,
        supervisor=supervisor,
        profile_extractor=profile_extractor,
    )

    runtime.run_turn("I'm a backend engineer thinking through this idea.")

    assert profile_extractor.calls
    assert runtime.get_user_profile().role == "Backend engineer"


def test_profile_extraction_is_off_by_default(tmp_path: Path) -> None:
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=SequenceFrameAnalyst([FrameAnalysis()]),
        supervisor=RecordingSupervisor(),
    )

    assert runtime.profile_extractor is None


def test_enabling_profile_extraction_auto_constructs_an_extractor(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        prompt_dir=tmp_path / "prompts",
        enable_profile_extraction=True,
        openrouter_api_key=SecretStr("test-key"),
    )

    runtime = ThinkingRuntime(
        settings=settings,
        frame_analyst=SequenceFrameAnalyst([FrameAnalysis()]),
        supervisor=RecordingSupervisor(),
    )

    assert isinstance(runtime.profile_extractor, ProfileExtractor)


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


def test_stream_turn_emits_node_events_and_a_final_turn_event(tmp_path: Path) -> None:
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

    events = list(runtime.stream_turn("Help me structure this product idea"))

    node_events = [event for event in events if event.type is TurnStreamEventType.NODE]
    turn_events = [event for event in events if event.type is TurnStreamEventType.TURN]
    assert node_events[0].node == "capture"
    assert "persist" in [event.node for event in node_events]
    assert len(turn_events) == 1
    turn = turn_events[0].turn
    assert turn is not None
    assert turn.mode is ThinkingMode.CAPTURE
    assert turn.message == "capture:Help me structure this product idea"

    saved = runtime.get_project_state(turn.project_id)
    assert saved is not None
    assert saved.north_star.problem_statement == "Notes are scattered"


def test_stream_turn_reports_current_mode_on_choose_mode_event(tmp_path: Path) -> None:
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

    events = list(runtime.stream_turn("Help me structure this product idea"))

    choose_mode_events = [event for event in events if event.node == "choose_mode"]
    assert len(choose_mode_events) == 1
    assert choose_mode_events[0].mode is ThinkingMode.CAPTURE


def test_stream_turn_rejects_blank_message_before_yielding(tmp_path: Path) -> None:
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=SequenceFrameAnalyst([FrameAnalysis()]),
        supervisor=RecordingSupervisor(),
    )

    with pytest.raises(ValueError, match="must not be blank"):
        runtime.stream_turn("   ")


def test_stream_turn_rejects_unknown_project_id_before_yielding(tmp_path: Path) -> None:
    runtime = _build_runtime(
        tmp_path,
        frame_analyst=SequenceFrameAnalyst([FrameAnalysis()]),
        supervisor=RecordingSupervisor(),
    )

    with pytest.raises(KeyError, match="Unknown project_id"):
        runtime.stream_turn("resume this", project_id="missing")


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
