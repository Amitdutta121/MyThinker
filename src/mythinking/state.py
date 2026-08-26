"""Typed domain state for thinking sessions and future LangGraph workflows."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid4().hex


class ThinkingMode(StrEnum):
    CAPTURE = "capture"
    CLARIFY = "clarify"
    CHALLENGE = "challenge"
    EXPLORE = "explore"
    RESEARCH = "research"
    CONVERGE = "converge"
    DECIDE = "decide"


class BranchStatus(StrEnum):
    ACTIVE = "active"
    PARKED = "parked"
    MERGED = "merged"
    DISCARDED = "discarded"


class EvidenceKind(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


class AssumptionStatus(StrEnum):
    UNTESTED = "untested"
    SUPPORTED = "supported"
    CHALLENGED = "challenged"
    REJECTED = "rejected"


class DriftStatus(StrEnum):
    ON_TRACK = "on_track"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    AMBIGUOUS = "ambiguous"
    DRIFTED = "drifted"


class TangentDisposition(StrEnum):
    NONE = "none"
    BRANCH = "branch"
    PARKED = "parked"


class DriftSignal(StrEnum):
    MISSING_ANCHOR = "missing_anchor"
    LOW_ANCHOR_OVERLAP = "low_anchor_overlap"
    EXPLICIT_TANGENT = "explicit_tangent"
    PARKING_LANGUAGE = "parking_language"
    MODEL_FALLBACK = "model_fallback"


class BranchCommandAction(StrEnum):
    NONE = "none"
    SWITCH = "switch"
    RETURN_TO_MAIN = "return_to_main"


class ResearchTaskStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DROPPED = "dropped"


class IntentAction(StrEnum):
    NONE = "none"
    EXPLORE = "explore"
    CONVERGE = "converge"


class ResearchTrigger(StrEnum):
    NONE = "none"
    EXPLICIT_REQUEST = "explicit_request"


class PlanTrigger(StrEnum):
    NONE = "none"
    EXPLICIT_REQUEST = "explicit_request"


class NorthStar(BaseModel):
    """The compact goal representation kept visible throughout a project."""

    title: str = "Untitled idea"
    problem_statement: str = ""
    desired_outcome: str = ""
    beneficiary: str = ""
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    current_hypothesis: str = ""
    next_action: str = ""


class IdeaBranch(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    summary: str = ""
    relationship_to_goal: str = ""
    status: BranchStatus = BranchStatus.ACTIVE
    revisit_trigger: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Assumption(BaseModel):
    id: str = Field(default_factory=new_id)
    statement: str
    status: AssumptionStatus = AssumptionStatus.UNTESTED
    importance: int = Field(default=3, ge=1, le=5)
    falsifying_evidence: str = ""


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=new_id)
    claim: str
    kind: EvidenceKind
    source_url: str = ""
    source_title: str = ""
    notes: str = ""
    captured_at: datetime = Field(default_factory=utc_now)


class ResearchTask(BaseModel):
    id: str = Field(default_factory=new_id)
    question: str
    status: ResearchTaskStatus = ResearchTaskStatus.OPEN
    notes: str = ""
    linked_evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class Decision(BaseModel):
    id: str = Field(default_factory=new_id)
    question: str
    choice: str
    rationale: str = ""
    alternatives: list[str] = Field(default_factory=list)
    reversible: bool = True
    decided_at: datetime = Field(default_factory=utc_now)


class NextAction(BaseModel):
    id: str = Field(default_factory=new_id)
    description: str
    success_signal: str = ""
    failure_signal: str = ""
    time_box_minutes: int = Field(default=30, ge=1)
    implementation_intention: str = ""
    completed: bool = False


class NorthStarUpdate(BaseModel):
    """Partial update emitted by the Frame Analyst."""

    title: str | None = None
    problem_statement: str | None = None
    desired_outcome: str | None = None
    beneficiary: str | None = None
    constraints_to_add: list[str] = Field(default_factory=list)
    success_criteria_to_add: list[str] = Field(default_factory=list)
    non_goals_to_add: list[str] = Field(default_factory=list)
    current_hypothesis: str | None = None
    next_action: str | None = None


class AssumptionDraft(BaseModel):
    """Structured assumption candidate before it is merged into persisted state."""

    statement: str
    importance: int = Field(default=3, ge=1, le=5)


class FrameAnalysis(BaseModel):
    """Structured frame update used by the M1 graph."""

    summary: str = ""
    north_star: NorthStarUpdate = Field(default_factory=NorthStarUpdate)
    assumptions_to_add: list[AssumptionDraft] = Field(default_factory=list)
    open_questions_to_add: list[str] = Field(default_factory=list)
    recommended_question: str = ""


class EvidenceDraft(BaseModel):
    """Structured evidence candidate before it is merged into persisted state."""

    claim: str
    kind: EvidenceKind
    source_url: str = ""
    source_title: str = ""
    notes: str = ""


class ResearchTaskDraft(BaseModel):
    """Structured research task candidate before it is merged into persisted state."""

    question: str
    notes: str = ""


class EvidenceAnalysis(BaseModel):
    """Structured evidence-ledger update used by the M3 graph."""

    summary: str = ""
    evidence_to_add: list[EvidenceDraft] = Field(default_factory=list)
    research_tasks_to_add: list[ResearchTaskDraft] = Field(default_factory=list)


class AlternativeDraft(BaseModel):
    """Structured alternative candidate before it is merged into persisted state."""

    name: str
    summary: str = ""
    relationship_to_goal: str = ""


class ExplorerAnalysis(BaseModel):
    """Structured divergent-alternatives update used by the M4 graph."""

    summary: str = ""
    alternatives_to_add: list[AlternativeDraft] = Field(default_factory=list)


class ConvergenceOption(BaseModel):
    """A branch the Synthesizer weighed while converging toward a recommendation."""

    branch_name: str
    tradeoffs: str = ""


class SynthesizerAnalysis(BaseModel):
    """Structured convergence update used by the M4 graph."""

    summary: str = ""
    options_considered: list[ConvergenceOption] = Field(default_factory=list)
    recommended_choice: str = ""
    rationale: str = ""


class ExplorationIntent(BaseModel):
    """Deterministic classification of an explicit explore/converge request."""

    action: IntentAction = IntentAction.NONE
    matched_text: str = ""


class ResearchIntent(BaseModel):
    """Deterministic classification of an explicit request to enter research mode."""

    trigger: ResearchTrigger = ResearchTrigger.NONE
    research_task_id: str = ""
    matched_text: str = ""


class ResearcherAnalysis(BaseModel):
    """Structured scoped-research answer used by the M5 graph."""

    summary: str = ""
    answer: str = ""
    findings_to_add: list[EvidenceDraft] = Field(default_factory=list)
    task_resolved: bool = False


class NextActionDraft(BaseModel):
    """Structured next-action candidate before it is merged into persisted state."""

    description: str
    success_signal: str = ""
    failure_signal: str = ""
    time_box_minutes: int = Field(default=30, ge=1)
    implementation_intention: str = ""


class PlanIntent(BaseModel):
    """Deterministic classification of an explicit request to plan the next action."""

    trigger: PlanTrigger = PlanTrigger.NONE
    matched_text: str = ""


class PlannerAnalysis(BaseModel):
    """Structured next-action plan used by the M6b graph."""

    summary: str = ""
    next_actions_to_add: list[NextActionDraft] = Field(default_factory=list)


class DriftAssessment(BaseModel):
    """Drift classification for the current turn, deterministic or model-resolved."""

    status: DriftStatus = DriftStatus.ON_TRACK
    disposition: TangentDisposition = TangentDisposition.NONE
    reason: str = ""
    tangent_summary: str = ""
    branch_name: str = ""
    signals: list[DriftSignal] = Field(default_factory=list)


class DriftJudgment(BaseModel):
    """Structured fallback judgment returned by the model when heuristics are inconclusive."""

    status: DriftStatus = DriftStatus.ON_TRACK
    disposition: TangentDisposition = TangentDisposition.NONE
    reason: str = ""
    tangent_summary: str = ""
    branch_name: str = ""


class BranchCommand(BaseModel):
    """Deterministic classification of an explicit branch-navigation request."""

    action: BranchCommandAction = BranchCommandAction.NONE
    target_branch_id: str | None = None
    target_branch_name: str = ""
    matched_text: str = ""


class AssistantTurn(BaseModel):
    """Structured assistant response returned by the runtime."""

    project_id: str
    mode: ThinkingMode
    message: str = Field(min_length=1)
    question: str = ""


class TurnStreamEventType(StrEnum):
    NODE = "node"
    TURN = "turn"
    ERROR = "error"


class TurnStreamEvent(BaseModel):
    """One incremental event pushed while a turn streams through the graph.

    `node`/`mode` are populated for `NODE` events (the graph node that just
    ran, and the project's current mode if that node touched `project_state`).
    `turn` is populated for the terminal `TURN` event. `detail` is populated
    for `ERROR` events raised mid-stream, after the HTTP response has already
    started, so it is delivered as data instead of an HTTP status.
    """

    type: TurnStreamEventType
    node: str = ""
    mode: ThinkingMode | None = None
    turn: AssistantTurn | None = None
    detail: str = ""


class ProjectState(BaseModel):
    """Serializable source of truth for one thinking project."""

    model_config = ConfigDict(validate_assignment=True)

    schema_version: int = 1
    project_id: str = Field(default_factory=new_id)
    north_star: NorthStar = Field(default_factory=NorthStar)
    current_mode: ThinkingMode = ThinkingMode.CAPTURE
    active_branch_id: str | None = None
    branches: list[IdeaBranch] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    research_tasks: list[ResearchTask] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    parked_ideas: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def active_branch_must_exist(self) -> "ProjectState":
        if self.active_branch_id and not any(
            branch.id == self.active_branch_id for branch in self.branches
        ):
            raise ValueError("active_branch_id must reference an existing branch")
        return self

    def mark_updated(self) -> None:
        self.updated_at = utc_now()


class SessionGraphState(BaseModel):
    """Thread-scoped state passed through the LangGraph workflow."""

    project_state: ProjectState
    user_message: str = Field(min_length=1)
    branch_command: BranchCommand | None = None
    frame_analysis: FrameAnalysis | None = None
    drift_assessment: DriftAssessment | None = None
    evidence_analysis: EvidenceAnalysis | None = None
    exploration_intent: ExplorationIntent | None = None
    exploration_analysis: ExplorerAnalysis | None = None
    synthesis: SynthesizerAnalysis | None = None
    research_intent: ResearchIntent | None = None
    research_analysis: ResearcherAnalysis | None = None
    plan_intent: PlanIntent | None = None
    planner_analysis: PlannerAnalysis | None = None
    assistant_turn: AssistantTurn | None = None
