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


class ResearchTaskStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DROPPED = "dropped"


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
    stale: bool = False


class DirectionProposal(BaseModel):
    """An assistant recommendation for the project's direction, not yet committed.

    Written only by `converge_ideas`; cleared by `commit_proposed_direction`.
    A proposal is never a decision -- the committed direction lives in
    `NorthStar.current_hypothesis` and is only set on explicit user authorization.
    """

    statement: str
    rationale: str = ""
    alternatives_considered: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


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


class PlannerAnalysis(BaseModel):
    """Structured next-action plan used by the M6b graph."""

    summary: str = ""
    next_actions_to_add: list[NextActionDraft] = Field(default_factory=list)


class UserProfile(BaseModel):
    """Cross-project facts about the user, off by default (M6c).

    Deliberately narrow: only stable, low-sensitivity, explicitly-stated
    facts that help tailor collaboration (role, expertise, working style).
    Never a place for sensitive personal details -- see
    `prompts/profile_extractor.v1.yaml`.
    """

    role: str = ""
    expertise: list[str] = Field(default_factory=list)
    working_style: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class UserProfileUpdate(BaseModel):
    """Partial update emitted by the Profile Extractor."""

    role: str | None = None
    expertise_to_add: list[str] = Field(default_factory=list)
    working_style_to_add: list[str] = Field(default_factory=list)


class ProfileAnalysis(BaseModel):
    """Structured user-profile update used by the M6c graph."""

    summary: str = ""
    profile_update: UserProfileUpdate = Field(default_factory=UserProfileUpdate)


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

    schema_version: int = 2
    project_id: str = Field(default_factory=new_id)
    north_star: NorthStar = Field(default_factory=NorthStar)
    current_mode: ThinkingMode = ThinkingMode.CAPTURE
    proposal: DirectionProposal | None = None
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
