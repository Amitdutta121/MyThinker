from pathlib import Path

from langchain_core.embeddings import Embeddings

from mythinking.graph import (
    apply_frame_analysis,
    build_thinking_graph,
    capture_node,
    choose_mode,
)
from mythinking.persistence import ProfileRepository, StateRepository
from mythinking.retrieval import open_document_store, search_content
from mythinking.state import (
    AlternativeDraft,
    AssistantTurn,
    AssumptionDraft,
    BranchCommand,
    BranchStatus,
    ConvergenceOption,
    DriftAssessment,
    DriftStatus,
    EvidenceAnalysis,
    EvidenceDraft,
    EvidenceKind,
    ExplorerAnalysis,
    FrameAnalysis,
    IdeaBranch,
    IntentAction,
    IntentClassification,
    NextActionDraft,
    NorthStarUpdate,
    PlanIntent,
    PlannerAnalysis,
    PlanTrigger,
    ProfileAnalysis,
    ProjectState,
    ResearcherAnalysis,
    ResearchIntent,
    ResearchTask,
    ResearchTaskDraft,
    ResearchTaskStatus,
    ResearchTrigger,
    SessionGraphState,
    SynthesizerAnalysis,
    ThinkingMode,
    TurnIntent,
    UserProfile,
    UserProfileUpdate,
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
            tuple[
                ProjectState,
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
                project_state,
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


class FakeIntentClassifier:
    def __init__(self, intent: TurnIntent = TurnIntent.NONE) -> None:
        self.intent = intent
        self.calls: list[str] = []

    def classify(self, user_message: str) -> IntentClassification:
        self.calls.append(user_message)
        return IntentClassification(intent=self.intent)


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


def test_choose_mode_returns_research_for_an_explicit_research_intent() -> None:
    project_state = ProjectState()

    mode = choose_mode(
        project_state,
        FrameAnalysis(),
        None,
        None,
        ResearchIntent(trigger=ResearchTrigger.EXPLICIT_REQUEST),
    )

    assert mode is ThinkingMode.RESEARCH


def test_choose_mode_returns_decide_for_an_explicit_plan_intent() -> None:
    project_state = ProjectState()

    mode = choose_mode(
        project_state,
        FrameAnalysis(),
        None,
        None,
        None,
        PlanIntent(trigger=PlanTrigger.EXPLICIT_REQUEST),
    )

    assert mode is ThinkingMode.DECIDE


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
    graph = build_thinking_graph(frame_analyst, supervisor, repository, FakeIntentClassifier())

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
    graph = build_thinking_graph(frame_analyst, supervisor, repository, FakeIntentClassifier())

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
    graph = build_thinking_graph(frame_analyst, supervisor, repository, FakeIntentClassifier())
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
    graph = build_thinking_graph(frame_analyst, supervisor, repository, FakeIntentClassifier())
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


class FakeDriftJudge:
    def __init__(self, resolved: DriftAssessment) -> None:
        self.resolved = resolved
        self.calls: list[tuple[ProjectState, str, DriftAssessment]] = []

    def resolve(
        self,
        project_state: ProjectState,
        user_message: str,
        assessment: DriftAssessment,
    ) -> DriftAssessment:
        self.calls.append((project_state, user_message, assessment))
        return self.resolved


def _anchored_project_state() -> ProjectState:
    project_state = ProjectState()
    project_state.north_star.problem_statement = "Product idea notes are scattered"
    project_state.north_star.desired_outcome = "Keep the idea thread focused"
    project_state.north_star.beneficiary = "Solo founder"
    return project_state


def test_ambiguous_drift_without_a_judge_falls_back_to_frame_merge(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    analysis = FrameAnalysis(north_star=NorthStarUpdate(current_hypothesis="Try a narrow beta"))
    frame_analyst = FakeFrameAnalyst(analysis)
    supervisor = FakeSupervisor()
    graph = build_thinking_graph(frame_analyst, supervisor, repository, FakeIntentClassifier())

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="Focus on the riskiest part first.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.drift_assessment is not None
    assert result.drift_assessment.status is DriftStatus.AMBIGUOUS
    assert result.project_state.current_mode is not ThinkingMode.CHALLENGE
    assert result.project_state.north_star.current_hypothesis == "Try a narrow beta"


def test_ambiguous_drift_resolved_by_judge_can_trigger_challenge_mode(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    resolved = DriftAssessment(
        status=DriftStatus.DRIFTED,
        tangent_summary="Focus on the riskiest part first",
        branch_name="Riskiest Part",
    )
    judge = FakeDriftJudge(resolved)
    graph = build_thinking_graph(
        frame_analyst, supervisor, repository, FakeIntentClassifier(), drift_judge=judge
    )

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="Focus on the riskiest part first.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert judge.calls
    assert result.project_state.current_mode is ThinkingMode.CHALLENGE
    assert result.project_state.branches
    assert result.project_state.branches[0].summary == "Focus on the riskiest part first"


def test_build_thinking_graph_switches_active_branch_and_skips_frame(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    graph = build_thinking_graph(frame_analyst, supervisor, repository, FakeIntentClassifier())

    project_state = _anchored_project_state()
    project_state.branches = [
        IdeaBranch(
            name="Newsletter Idea",
            summary="Start a newsletter for solo founders",
            status=BranchStatus.PARKED,
        )
    ]

    initial_state = SessionGraphState(
        project_state=project_state,
        user_message="Let's switch to the newsletter branch.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert frame_analyst.calls == []
    assert result.branch_command is not None
    assert result.branch_command.target_branch_name == "Newsletter Idea"
    assert result.project_state.active_branch_id == project_state.branches[0].id
    assert result.project_state.branches[0].status is BranchStatus.ACTIVE
    assert supervisor.calls[0][4] is not None
    assert supervisor.calls[0][4].target_branch_name == "Newsletter Idea"


class FakeEvidenceAnalyst:
    def __init__(self, analysis: EvidenceAnalysis) -> None:
        self.analysis = analysis
        self.calls: list[tuple[ProjectState, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> EvidenceAnalysis:
        self.calls.append((project_state, user_message))
        return self.analysis


def test_build_thinking_graph_merges_extracted_evidence_into_project_state(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    evidence_analyst = FakeEvidenceAnalyst(
        EvidenceAnalysis(
            evidence_to_add=[
                EvidenceDraft(
                    claim="Remote work always reduces innovation",
                    kind=EvidenceKind.HYPOTHESIS,
                )
            ]
        )
    )
    graph = build_thinking_graph(
        frame_analyst,
        supervisor,
        repository,
        FakeIntentClassifier(),
        evidence_analyst=evidence_analyst,
    )

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="Remote work always reduces innovation, so require office attendance.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert evidence_analyst.calls
    assert result.evidence_analysis is not None
    assert len(result.project_state.evidence) == 1
    assert result.project_state.evidence[0].kind is EvidenceKind.HYPOTHESIS


def test_build_thinking_graph_skips_evidence_extraction_without_an_analyst(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    graph = build_thinking_graph(frame_analyst, supervisor, repository, FakeIntentClassifier())

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="The first experiment should be a local CLI capture loop.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.evidence_analysis is None
    assert result.project_state.evidence == []


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text) % 5), 1.0]


def test_build_thinking_graph_indexes_newly_added_evidence_and_research_tasks(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    evidence_analyst = FakeEvidenceAnalyst(
        EvidenceAnalysis(
            evidence_to_add=[
                EvidenceDraft(
                    claim="Remote work always reduces innovation", kind=EvidenceKind.HYPOTHESIS
                )
            ],
            research_tasks_to_add=[
                ResearchTaskDraft(question="Does remote work reduce innovation?")
            ],
        )
    )

    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=2) as store:
        graph = build_thinking_graph(
            frame_analyst,
            supervisor,
            repository,
            FakeIntentClassifier(),
            evidence_analyst=evidence_analyst,
            store=store,
        )

        initial_state = SessionGraphState(
            project_state=_anchored_project_state(),
            user_message="Remote work always reduces innovation, so require office attendance.",
        )

        result = SessionGraphState.model_validate(graph.invoke(initial_state))

        evidence_hits = search_content(
            store, result.project_state.project_id, "evidence", "remote work", top_k=5
        )
        task_hits = search_content(
            store, result.project_state.project_id, "research_task", "remote work", top_k=5
        )
        assert len(evidence_hits) == 1
        assert len(task_hits) == 1


def test_build_thinking_graph_skips_evidence_extraction_for_branch_commands(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    evidence_analyst = FakeEvidenceAnalyst(EvidenceAnalysis())
    graph = build_thinking_graph(
        frame_analyst,
        supervisor,
        repository,
        FakeIntentClassifier(),
        evidence_analyst=evidence_analyst,
    )

    project_state = _anchored_project_state()
    project_state.branches = [
        IdeaBranch(
            name="Newsletter Idea",
            summary="Start a newsletter for solo founders",
            status=BranchStatus.PARKED,
        )
    ]
    initial_state = SessionGraphState(
        project_state=project_state,
        user_message="Let's switch to the newsletter branch.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert evidence_analyst.calls == []
    assert result.evidence_analysis is None


class FakeExplorer:
    def __init__(self, analysis: ExplorerAnalysis) -> None:
        self.analysis = analysis
        self.calls: list[tuple[ProjectState, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> ExplorerAnalysis:
        self.calls.append((project_state, user_message))
        return self.analysis


class FakeSynthesizer:
    def __init__(self, analysis: SynthesizerAnalysis) -> None:
        self.analysis = analysis
        self.calls: list[tuple[ProjectState, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> SynthesizerAnalysis:
        self.calls.append((project_state, user_message))
        return self.analysis


def test_build_thinking_graph_routes_explore_requests_and_adds_branches(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    explorer = FakeExplorer(
        ExplorerAnalysis(
            alternatives_to_add=[
                AlternativeDraft(name="Newsletter", summary="Start a weekly newsletter"),
                AlternativeDraft(name="Community", summary="Start a paid community"),
            ]
        )
    )
    graph = build_thinking_graph(
        frame_analyst,
        supervisor,
        repository,
        FakeIntentClassifier(TurnIntent.EXPLORE),
        explorer=explorer,
    )

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="Can you give me some alternatives for this idea?",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert explorer.calls
    assert frame_analyst.calls == []
    assert result.exploration_intent is not None
    assert result.exploration_intent.action is IntentAction.EXPLORE
    assert result.project_state.current_mode is ThinkingMode.EXPLORE
    assert [branch.name for branch in result.project_state.branches] == [
        "Newsletter",
        "Community",
    ]


def test_build_thinking_graph_routes_converge_requests_and_merges_branches(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    synthesizer = FakeSynthesizer(
        SynthesizerAnalysis(
            options_considered=[ConvergenceOption(branch_name="Newsletter Idea")],
            recommended_choice="Start with the newsletter",
        )
    )
    graph = build_thinking_graph(
        frame_analyst,
        supervisor,
        repository,
        FakeIntentClassifier(TurnIntent.CONVERGE),
        synthesizer=synthesizer,
    )

    project_state = _anchored_project_state()
    project_state.branches = [
        IdeaBranch(
            name="Newsletter Idea",
            summary="Start a newsletter for solo founders",
            status=BranchStatus.ACTIVE,
        )
    ]
    initial_state = SessionGraphState(
        project_state=project_state,
        user_message="Help me decide between these options.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert synthesizer.calls
    assert frame_analyst.calls == []
    assert result.exploration_intent is not None
    assert result.exploration_intent.action is IntentAction.CONVERGE
    assert result.project_state.current_mode is ThinkingMode.CONVERGE
    assert result.project_state.branches[0].status is BranchStatus.MERGED
    assert result.project_state.north_star.current_hypothesis == "Start with the newsletter"


def test_build_thinking_graph_skips_explore_and_converge_without_specialists(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    intent_classifier = FakeIntentClassifier(TurnIntent.EXPLORE)
    graph = build_thinking_graph(frame_analyst, supervisor, repository, intent_classifier)

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="Can you give me some alternatives for this idea?",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.exploration_analysis is None
    assert result.project_state.branches == []
    assert result.project_state.current_mode is ThinkingMode.EXPLORE


class FakeResearcher:
    def __init__(self, analysis: ResearcherAnalysis) -> None:
        self.analysis = analysis
        self.calls: list[tuple[ProjectState, str, ResearchTask | None]] = []

    def analyze(
        self,
        project_state: ProjectState,
        user_message: str,
        research_task: ResearchTask | None = None,
    ) -> ResearcherAnalysis:
        self.calls.append((project_state, user_message, research_task))
        return self.analysis


def test_build_thinking_graph_routes_research_requests_and_imports_evidence(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    researcher = FakeResearcher(
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
    graph = build_thinking_graph(
        frame_analyst,
        supervisor,
        repository,
        FakeIntentClassifier(TurnIntent.RESEARCH),
        researcher=researcher,
    )

    project_state = _anchored_project_state()
    task = ResearchTask(question="Do we ship weekly?")
    project_state.research_tasks = [task]
    initial_state = SessionGraphState(
        project_state=project_state,
        user_message="Can you research whether we ship weekly?",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert researcher.calls
    assert frame_analyst.calls == []
    assert result.research_intent is not None
    assert result.research_intent.trigger is ResearchTrigger.EXPLICIT_REQUEST
    assert result.research_intent.research_task_id == task.id
    assert result.project_state.current_mode is ThinkingMode.RESEARCH
    assert len(result.project_state.evidence) == 1
    assert result.project_state.research_tasks[0].status is ResearchTaskStatus.ANSWERED


def test_build_thinking_graph_skips_research_without_a_researcher(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    intent_classifier = FakeIntentClassifier(TurnIntent.RESEARCH)
    graph = build_thinking_graph(frame_analyst, supervisor, repository, intent_classifier)

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="Can you research this for me?",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.research_analysis is None
    assert result.project_state.evidence == []
    assert result.project_state.current_mode is ThinkingMode.RESEARCH


def test_build_thinking_graph_indexes_evidence_found_during_research(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    researcher = FakeResearcher(
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

    with open_document_store(tmp_path / "store.sqlite", _FakeEmbeddings(), dimensions=2) as store:
        graph = build_thinking_graph(
            frame_analyst,
            supervisor,
            repository,
            FakeIntentClassifier(TurnIntent.RESEARCH),
            researcher=researcher,
            store=store,
        )

        project_state = _anchored_project_state()
        task = ResearchTask(question="Do we ship weekly?")
        project_state.research_tasks = [task]
        initial_state = SessionGraphState(
            project_state=project_state,
            user_message="Can you research whether we ship weekly?",
        )

        result = SessionGraphState.model_validate(graph.invoke(initial_state))

        hits = search_content(
            store, result.project_state.project_id, "evidence", "weekly releases", top_k=5
        )
        assert len(hits) == 1


class FakePlanner:
    def __init__(self, analysis: PlannerAnalysis) -> None:
        self.analysis = analysis
        self.calls: list[tuple[ProjectState, str]] = []

    def analyze(self, project_state: ProjectState, user_message: str) -> PlannerAnalysis:
        self.calls.append((project_state, user_message))
        return self.analysis


def test_build_thinking_graph_routes_planning_requests_and_adds_next_actions(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    planner = FakePlanner(
        PlannerAnalysis(
            next_actions_to_add=[
                NextActionDraft(
                    description="Draft the first newsletter issue",
                    time_box_minutes=30,
                )
            ]
        )
    )
    graph = build_thinking_graph(
        frame_analyst,
        supervisor,
        repository,
        FakeIntentClassifier(TurnIntent.PLAN),
        planner=planner,
    )

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="What should I do next?",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert planner.calls
    assert frame_analyst.calls == []
    assert result.plan_intent is not None
    assert result.plan_intent.trigger is PlanTrigger.EXPLICIT_REQUEST
    assert result.project_state.current_mode is ThinkingMode.DECIDE
    assert [action.description for action in result.project_state.next_actions] == [
        "Draft the first newsletter issue"
    ]


def test_build_thinking_graph_skips_planning_without_a_planner(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    intent_classifier = FakeIntentClassifier(TurnIntent.PLAN)
    graph = build_thinking_graph(frame_analyst, supervisor, repository, intent_classifier)

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="What should I do next?",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.planner_analysis is None
    assert result.project_state.next_actions == []
    assert result.project_state.current_mode is ThinkingMode.DECIDE


class FakeProfileExtractor:
    def __init__(self, analysis: ProfileAnalysis) -> None:
        self.analysis = analysis
        self.calls: list[tuple[UserProfile, str]] = []

    def analyze(self, user_profile: UserProfile, user_message: str) -> ProfileAnalysis:
        self.calls.append((user_profile, user_message))
        return self.analysis


def test_build_thinking_graph_extracts_and_persists_profile_on_the_frame_path(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    profile_repository = ProfileRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    profile_extractor = FakeProfileExtractor(
        ProfileAnalysis(profile_update=UserProfileUpdate(role="Backend engineer"))
    )
    graph = build_thinking_graph(
        frame_analyst,
        supervisor,
        repository,
        FakeIntentClassifier(),
        profile_extractor=profile_extractor,
        profile_repository=profile_repository,
    )

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="I'm a backend engineer thinking through this idea.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert profile_extractor.calls
    assert result.profile_analysis is not None
    assert result.profile_analysis.profile_update.role == "Backend engineer"
    assert profile_repository.load().role == "Backend engineer"


def test_build_thinking_graph_skips_profile_extraction_without_an_extractor(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    frame_analyst = FakeFrameAnalyst(FrameAnalysis())
    supervisor = FakeSupervisor()
    graph = build_thinking_graph(frame_analyst, supervisor, repository, FakeIntentClassifier())

    initial_state = SessionGraphState(
        project_state=_anchored_project_state(),
        user_message="I'm a backend engineer thinking through this idea.",
    )

    result = SessionGraphState.model_validate(graph.invoke(initial_state))

    assert result.profile_analysis is None
