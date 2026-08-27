"""LangGraph workflow for the core loop, M2 drift control, and M3 evidence."""

from collections.abc import Iterable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.store.sqlite import SqliteStore

from mythinking.agents.evidence_analyst import EvidenceAnalyst
from mythinking.agents.explorer import Explorer
from mythinking.agents.frame_analyst import FrameAnalyst
from mythinking.agents.intent_classifier import IntentClassifier
from mythinking.agents.planner import Planner
from mythinking.agents.profile_extractor import ProfileExtractor
from mythinking.agents.researcher import Researcher
from mythinking.agents.supervisor import SupervisorAgent
from mythinking.agents.synthesizer import Synthesizer
from mythinking.branching import BranchManager, BranchSwitcher
from mythinking.drift import DriftDetector, DriftJudge, DriftResolver
from mythinking.evidence import EvidenceLedger
from mythinking.exploration import ConvergenceService, ExplorationManager
from mythinking.persistence import ProfileRepository, StateRepository
from mythinking.planning import PlanningService
from mythinking.profile import ProfileService
from mythinking.research import ResearchImporter, best_matching_open_task
from mythinking.retrieval import index_content
from mythinking.state import (
    Assumption,
    BranchCommandAction,
    DriftAssessment,
    DriftStatus,
    ExplorationIntent,
    FrameAnalysis,
    IntentAction,
    PlanIntent,
    PlanTrigger,
    ProjectState,
    ResearchIntent,
    ResearchTask,
    ResearchTrigger,
    SessionGraphState,
    ThinkingMode,
    TurnIntent,
)


def build_thinking_graph(
    frame_analyst: FrameAnalyst,
    supervisor: SupervisorAgent,
    repository: StateRepository,
    intent_classifier: IntentClassifier,
    *,
    drift_detector: DriftDetector | None = None,
    drift_judge: DriftJudge | None = None,
    branch_manager: BranchManager | None = None,
    branch_switcher: BranchSwitcher | None = None,
    evidence_analyst: EvidenceAnalyst | None = None,
    evidence_ledger: EvidenceLedger | None = None,
    explorer: Explorer | None = None,
    synthesizer: Synthesizer | None = None,
    exploration_manager: ExplorationManager | None = None,
    convergence_service: ConvergenceService | None = None,
    researcher: Researcher | None = None,
    research_importer: ResearchImporter | None = None,
    planner: Planner | None = None,
    planning_service: PlanningService | None = None,
    profile_extractor: ProfileExtractor | None = None,
    profile_repository: ProfileRepository | None = None,
    profile_service: ProfileService | None = None,
    checkpointer: Any = None,
    store: SqliteStore | None = None,
):
    workflow = StateGraph(SessionGraphState)
    drift_resolver = DriftResolver(drift_detector or DriftDetector(), drift_judge)
    branch_manager = branch_manager or BranchManager()
    branch_switcher = branch_switcher or BranchSwitcher()
    evidence_ledger = evidence_ledger or EvidenceLedger()
    exploration_manager = exploration_manager or ExplorationManager()
    convergence_service = convergence_service or ConvergenceService()
    research_importer = research_importer or ResearchImporter()
    planning_service = planning_service or PlanningService()
    profile_service = profile_service or ProfileService()

    workflow.add_node("capture", capture_node)
    workflow.add_node("handle_branch_command", _branch_command_node(branch_switcher))
    workflow.add_node("classify_intent", _classify_intent_node(intent_classifier))
    workflow.add_node("explore", _explore_node(explorer, exploration_manager))
    workflow.add_node("converge", _converge_node(synthesizer, convergence_service))
    workflow.add_node("research", _research_node(researcher, research_importer, store))
    workflow.add_node("plan", _plan_node(planner, planning_service))
    workflow.add_node("frame", _frame_node(frame_analyst))
    workflow.add_node("detect_drift", _drift_node(drift_resolver, branch_manager))
    workflow.add_node("extract_evidence", _evidence_node(evidence_analyst, evidence_ledger, store))
    workflow.add_node(
        "extract_profile",
        _profile_node(profile_extractor, profile_service, profile_repository),
    )
    workflow.add_node("choose_mode", choose_mode_node)
    workflow.add_node("respond", _respond_node(supervisor))
    workflow.add_node("persist", _persist_node(repository))

    workflow.add_edge(START, "capture")
    workflow.add_edge("capture", "handle_branch_command")
    workflow.add_conditional_edges(
        "handle_branch_command",
        _route_after_branch_command,
        {"continue": "classify_intent", "handled": "choose_mode"},
    )
    workflow.add_conditional_edges(
        "classify_intent",
        _route_after_intent_classification,
        {
            "explore": "explore",
            "converge": "converge",
            "research": "research",
            "plan": "plan",
            "none": "frame",
        },
    )
    workflow.add_edge("explore", "choose_mode")
    workflow.add_edge("converge", "choose_mode")
    workflow.add_edge("research", "choose_mode")
    workflow.add_edge("plan", "choose_mode")
    workflow.add_edge("frame", "detect_drift")
    workflow.add_edge("detect_drift", "extract_evidence")
    workflow.add_edge("extract_evidence", "extract_profile")
    workflow.add_edge("extract_profile", "choose_mode")
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
        state.exploration_intent,
        state.research_intent,
        state.plan_intent,
    )
    return {"project_state": project_state}


def _respond_node(supervisor: SupervisorAgent):
    def run(state: SessionGraphState) -> dict[str, Any]:
        assistant_turn = supervisor.respond(
            state.project_state,
            state.user_message,
            state.frame_analysis,
            state.drift_assessment,
            state.branch_command,
            state.exploration_analysis,
            state.synthesis,
            state.research_analysis,
            state.planner_analysis,
        )
        return {"assistant_turn": assistant_turn}

    return run


def _classify_intent_node(intent_classifier: IntentClassifier):
    def run(state: SessionGraphState) -> dict[str, Any]:
        classification = intent_classifier.classify(state.user_message)
        exploration_intent = ExplorationIntent()
        research_intent = ResearchIntent()
        plan_intent = PlanIntent()

        if classification.intent is TurnIntent.EXPLORE:
            exploration_intent = ExplorationIntent(
                action=IntentAction.EXPLORE, matched_text=state.user_message
            )
        elif classification.intent is TurnIntent.CONVERGE:
            exploration_intent = ExplorationIntent(
                action=IntentAction.CONVERGE, matched_text=state.user_message
            )
        elif classification.intent is TurnIntent.RESEARCH:
            task = best_matching_open_task(state.project_state, state.user_message)
            research_intent = ResearchIntent(
                trigger=ResearchTrigger.EXPLICIT_REQUEST,
                research_task_id=task.id if task else "",
                matched_text=state.user_message,
            )
        elif classification.intent is TurnIntent.PLAN:
            plan_intent = PlanIntent(
                trigger=PlanTrigger.EXPLICIT_REQUEST, matched_text=state.user_message
            )

        return {
            "intent_classification": classification,
            "exploration_intent": exploration_intent,
            "research_intent": research_intent,
            "plan_intent": plan_intent,
        }

    return run


def _route_after_intent_classification(state: SessionGraphState) -> str:
    classification = state.intent_classification
    if classification is None:
        return "none"
    if classification.intent is TurnIntent.EXPLORE:
        return "explore"
    if classification.intent is TurnIntent.CONVERGE:
        return "converge"
    if classification.intent is TurnIntent.RESEARCH:
        return "research"
    if classification.intent is TurnIntent.PLAN:
        return "plan"
    return "none"


def _explore_node(explorer: Explorer | None, exploration_manager: ExplorationManager):
    def run(state: SessionGraphState) -> dict[str, Any]:
        if explorer is None:
            return {}
        analysis = explorer.analyze(state.project_state, state.user_message)
        project_state = exploration_manager.merge(state.project_state, analysis)
        return {"exploration_analysis": analysis, "project_state": project_state}

    return run


def _converge_node(synthesizer: Synthesizer | None, convergence_service: ConvergenceService):
    def run(state: SessionGraphState) -> dict[str, Any]:
        if synthesizer is None:
            return {}
        analysis = synthesizer.analyze(state.project_state, state.user_message)
        project_state = convergence_service.merge(state.project_state, analysis)
        return {"synthesis": analysis, "project_state": project_state}

    return run


def _research_node(
    researcher: Researcher | None,
    research_importer: ResearchImporter,
    store: SqliteStore | None,
):
    def run(state: SessionGraphState) -> dict[str, Any]:
        if researcher is None:
            return {}
        intent = state.research_intent
        research_task_id = intent.research_task_id if intent else ""
        task = _find_research_task(state.project_state, research_task_id)
        before_evidence_ids = {item.id for item in state.project_state.evidence}
        analysis = researcher.analyze(state.project_state, state.user_message, task)
        project_state = research_importer.merge(state.project_state, research_task_id, analysis)
        if store is not None:
            _index_new_evidence(store, project_state, before_evidence_ids)
        return {"research_analysis": analysis, "project_state": project_state}

    return run


def _find_research_task(project_state: ProjectState, research_task_id: str) -> ResearchTask | None:
    if not research_task_id:
        return None
    return next(
        (task for task in project_state.research_tasks if task.id == research_task_id),
        None,
    )


def _plan_node(planner: Planner | None, planning_service: PlanningService):
    def run(state: SessionGraphState) -> dict[str, Any]:
        if planner is None:
            return {}
        analysis = planner.analyze(state.project_state, state.user_message)
        project_state = planning_service.merge(state.project_state, analysis)
        return {"planner_analysis": analysis, "project_state": project_state}

    return run


def _branch_command_node(branch_switcher: BranchSwitcher):
    def run(state: SessionGraphState) -> dict[str, Any]:
        command = branch_switcher.detect(state.project_state, state.user_message)
        if command.action is BranchCommandAction.NONE:
            return {"branch_command": command}
        project_state = branch_switcher.apply(state.project_state, command)
        return {"branch_command": command, "project_state": project_state}

    return run


def _evidence_node(
    evidence_analyst: EvidenceAnalyst | None,
    evidence_ledger: EvidenceLedger,
    store: SqliteStore | None,
):
    def run(state: SessionGraphState) -> dict[str, Any]:
        if evidence_analyst is None:
            return {}
        analysis = evidence_analyst.analyze(state.project_state, state.user_message)
        before_evidence_ids = {item.id for item in state.project_state.evidence}
        before_task_ids = {task.id for task in state.project_state.research_tasks}
        project_state = evidence_ledger.merge(state.project_state, analysis)
        if store is not None:
            _index_new_evidence(store, project_state, before_evidence_ids)
            _index_new_research_tasks(store, project_state, before_task_ids)
        return {"evidence_analysis": analysis, "project_state": project_state}

    return run


def _index_new_evidence(
    store: SqliteStore, project_state: ProjectState, before_ids: set[str]
) -> None:
    for item in project_state.evidence:
        if item.id in before_ids:
            continue
        index_content(
            store,
            project_state.project_id,
            "evidence",
            item.id,
            item.claim,
            kind=item.kind.value,
            source_url=item.source_url,
            source_title=item.source_title,
        )


def _index_new_research_tasks(
    store: SqliteStore, project_state: ProjectState, before_ids: set[str]
) -> None:
    for task in project_state.research_tasks:
        if task.id in before_ids:
            continue
        index_content(
            store,
            project_state.project_id,
            "research_task",
            task.id,
            task.question,
            notes=task.notes,
        )


def _profile_node(
    profile_extractor: ProfileExtractor | None,
    profile_service: ProfileService,
    profile_repository: ProfileRepository | None,
):
    def run(state: SessionGraphState) -> dict[str, Any]:
        if profile_extractor is None or profile_repository is None:
            return {}
        profile = profile_repository.load()
        analysis = profile_extractor.analyze(profile, state.user_message)
        profile_repository.save(profile_service.merge(profile, analysis))
        return {"profile_analysis": analysis}

    return run


def _route_after_branch_command(state: SessionGraphState) -> str:
    command = state.branch_command
    if command is not None and command.action is not BranchCommandAction.NONE:
        return "handled"
    return "continue"


def _persist_node(repository: StateRepository):
    def run(state: SessionGraphState) -> dict[str, ProjectState]:
        repository.save(state.project_state)
        return {"project_state": state.project_state}

    return run


def _drift_node(
    drift_resolver: DriftResolver,
    branch_manager: BranchManager,
):
    def run(state: SessionGraphState) -> dict[str, DriftAssessment | ProjectState]:
        assessment = drift_resolver.assess(state.project_state, state.user_message)
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
    exploration_intent: ExplorationIntent | None = None,
    research_intent: ResearchIntent | None = None,
    plan_intent: PlanIntent | None = None,
) -> ThinkingMode:
    if drift_assessment and drift_assessment.status is DriftStatus.DRIFTED:
        return ThinkingMode.CHALLENGE
    if exploration_intent is not None:
        if exploration_intent.action is IntentAction.EXPLORE:
            return ThinkingMode.EXPLORE
        if exploration_intent.action is IntentAction.CONVERGE:
            return ThinkingMode.CONVERGE
    if research_intent is not None and research_intent.trigger is ResearchTrigger.EXPLICIT_REQUEST:
        return ThinkingMode.RESEARCH
    if plan_intent is not None and plan_intent.trigger is PlanTrigger.EXPLICIT_REQUEST:
        return ThinkingMode.DECIDE

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
