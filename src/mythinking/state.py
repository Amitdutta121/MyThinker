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


class AssistantTurn(BaseModel):
    """Structured assistant response returned by the runtime."""

    project_id: str
    mode: ThinkingMode
    message: str = Field(min_length=1)
    question: str = ""


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
    frame_analysis: FrameAnalysis | None = None
    assistant_turn: AssistantTurn | None = None
