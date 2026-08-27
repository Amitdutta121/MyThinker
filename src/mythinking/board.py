"""Deterministic helpers over ProjectState: a mutable per-turn holder, display-mode
derivation, plan staleness, and the frame-analysis merge.

The single-agent architecture has no `choose_mode` router. `ThinkingMode` survives
only as a display label on `AssistantTurn` (the API and frontend still render it),
computed from persisted state after each turn by `derive_mode`.
"""

import threading
from collections.abc import Iterable
from dataclasses import dataclass, field

from mythinking.state import (
    Assumption,
    BranchStatus,
    FrameAnalysis,
    ProjectState,
    ThinkingMode,
)


@dataclass
class MutableStateHolder:
    """Carries the turn's `ProjectState` so tool closures can mutate it in place.

    Merge services return a fresh deep-copied `ProjectState`; tools reassign
    `holder.project_state` to it under `holder.lock`, so later tools (and the
    context-injection middleware) always see the latest board.
    """

    project_state: ProjectState
    lock: threading.RLock = field(default_factory=threading.RLock)


_CORE_FRAME_FIELDS = ("problem_statement", "desired_outcome", "beneficiary")


def core_frame_incomplete(state: ProjectState) -> bool:
    """True while any of the North Star's load-bearing fields is still blank."""
    return any(not getattr(state.north_star, field).strip() for field in _CORE_FRAME_FIELDS)


def active_branch_count(state: ProjectState) -> int:
    return sum(1 for branch in state.branches if branch.status == BranchStatus.ACTIVE)


def has_live_plan(state: ProjectState) -> bool:
    return any(not step.completed and not step.stale for step in state.next_actions)


def derive_mode(state: ProjectState) -> ThinkingMode:
    """Pick a display mode from persisted state alone. Advisory, not routing.

    Priority: unframed goal -> CLARIFY; open proposal awaiting commitment ->
    CONVERGE; committed direction with a live plan -> DECIDE; committed direction
    without a plan -> CAPTURE; multiple active alternatives and nothing committed
    -> EXPLORE; otherwise CAPTURE.
    """
    if core_frame_incomplete(state):
        return ThinkingMode.CLARIFY
    committed = bool(state.north_star.current_hypothesis.strip())
    if state.proposal is not None and not committed:
        return ThinkingMode.CONVERGE
    if committed:
        return ThinkingMode.DECIDE if has_live_plan(state) else ThinkingMode.CAPTURE
    if state.proposal is None and active_branch_count(state) >= 2:
        return ThinkingMode.EXPLORE
    return ThinkingMode.CAPTURE


def mark_plan_stale(state: ProjectState) -> None:
    """Flag every not-yet-done next action as stale (in place).

    Called when the committed direction changes or a decision lands, so an
    existing plan is visibly invalidated without being deleted.
    """
    for step in state.next_actions:
        if not step.completed:
            step.stale = True


def apply_frame_analysis(
    project_state: ProjectState, frame_analysis: FrameAnalysis
) -> ProjectState:
    """Fold a FrameAnalysis into a fresh copy of the project state (deterministic).

    Moved verbatim from the retired graph node so `set_north_star` can reuse it.
    """
    project = project_state.model_copy(deep=True)
    update = frame_analysis.north_star

    if update.title is not None:
        project.north_star.title = update.title.strip()
    if update.problem_statement is not None:
        project.north_star.problem_statement = update.problem_statement.strip()
    if update.desired_outcome is not None:
        project.north_star.desired_outcome = update.desired_outcome.strip()
    if update.beneficiary is not None:
        project.north_star.beneficiary = update.beneficiary.strip()
    if update.current_hypothesis is not None:
        project.north_star.current_hypothesis = update.current_hypothesis.strip()
    if update.next_action is not None:
        project.north_star.next_action = update.next_action.strip()

    project.north_star.constraints = _append_unique(
        project.north_star.constraints, update.constraints_to_add
    )
    project.north_star.success_criteria = _append_unique(
        project.north_star.success_criteria, update.success_criteria_to_add
    )
    project.north_star.non_goals = _append_unique(
        project.north_star.non_goals, update.non_goals_to_add
    )

    existing = {_normalize(item.statement) for item in project.assumptions}
    for draft in frame_analysis.assumptions_to_add:
        key = _normalize(draft.statement)
        if key and key not in existing:
            project.assumptions.append(
                Assumption(statement=draft.statement.strip(), importance=draft.importance)
            )
            existing.add(key)

    project.open_questions = _append_unique(
        project.open_questions, frame_analysis.open_questions_to_add
    )
    if frame_analysis.recommended_question.strip():
        project.open_questions = _append_unique(
            project.open_questions, [frame_analysis.recommended_question]
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
