"""Preserve detected tangents and handle explicit branch navigation."""

import re

from mythinking.state import (
    BranchCommand,
    BranchCommandAction,
    BranchStatus,
    DriftAssessment,
    DriftStatus,
    IdeaBranch,
    ProjectState,
    TangentDisposition,
)


class BranchManager:
    """Write drift-preservation updates into the persisted project state."""

    def preserve_tangent(
        self,
        project_state: ProjectState,
        assessment: DriftAssessment,
    ) -> ProjectState:
        project = project_state.model_copy(deep=True)
        if assessment.status is not DriftStatus.DRIFTED or not assessment.tangent_summary:
            return project

        if assessment.disposition is TangentDisposition.PARKED:
            if not _contains_normalized(project.parked_ideas, assessment.tangent_summary):
                project.parked_ideas.append(assessment.tangent_summary)
            return project

        branch_name = assessment.branch_name.strip() or "Preserved tangent"
        if _has_matching_branch(project, branch_name, assessment.tangent_summary):
            return project

        project.branches.append(
            IdeaBranch(
                name=branch_name,
                summary=assessment.tangent_summary,
                relationship_to_goal="Preserved while staying focused on the active North Star.",
                status=BranchStatus.PARKED,
                revisit_trigger=(
                    "Return after resolving the current goal or if this tangent becomes critical."
                ),
            )
        )
        return project


_RETURN_TRIGGERS = (
    "back to the main goal",
    "return to the main goal",
    "focus on the main goal",
    "back to the main thread",
    "return to the main thread",
    "back to the north star",
    "return to the north star",
    "return to the original goal",
    "back on track",
)

_SWITCH_TRIGGERS = (
    "switch back to",
    "switch to",
    "go back to",
    "pick back up",
    "continue with",
    "resume",
)

_MATCH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "back",
    "be",
    "branch",
    "but",
    "by",
    "for",
    "from",
    "go",
    "goal",
    "idea",
    "in",
    "into",
    "is",
    "it",
    "let",
    "lets",
    "main",
    "of",
    "on",
    "or",
    "our",
    "part",
    "pick",
    "resume",
    "return",
    "switch",
    "that",
    "the",
    "this",
    "thread",
    "to",
    "topic",
    "tangent",
    "we",
    "with",
    "you",
    "your",
}


class BranchSwitcher:
    """Deterministic parser and state mutator for explicit branch navigation."""

    def detect(self, project_state: ProjectState, user_message: str) -> BranchCommand:
        lowered = _normalize(user_message)
        if any(phrase in lowered for phrase in _RETURN_TRIGGERS):
            return BranchCommand(
                action=BranchCommandAction.RETURN_TO_MAIN,
                matched_text=user_message.strip(),
            )
        if not any(trigger in lowered for trigger in _SWITCH_TRIGGERS):
            return BranchCommand()

        candidate = _best_matching_branch(project_state, lowered)
        if candidate is None:
            return BranchCommand()
        return BranchCommand(
            action=BranchCommandAction.SWITCH,
            target_branch_id=candidate.id,
            target_branch_name=candidate.name,
            matched_text=user_message.strip(),
        )

    def apply(self, project_state: ProjectState, command: BranchCommand) -> ProjectState:
        project = project_state.model_copy(deep=True)
        if command.action is BranchCommandAction.RETURN_TO_MAIN:
            if project.active_branch_id:
                _set_branch_status(project, project.active_branch_id, BranchStatus.PARKED)
            project.active_branch_id = None
            return project

        if command.action is BranchCommandAction.SWITCH and command.target_branch_id:
            if project.active_branch_id and project.active_branch_id != command.target_branch_id:
                _set_branch_status(project, project.active_branch_id, BranchStatus.PARKED)
            _set_branch_status(project, command.target_branch_id, BranchStatus.ACTIVE)
            project.active_branch_id = command.target_branch_id
        return project


def _best_matching_branch(project_state: ProjectState, lowered_message: str) -> IdeaBranch | None:
    message_tokens = _match_tokens(lowered_message)
    best_branch: IdeaBranch | None = None
    best_overlap = 0
    for branch in project_state.branches:
        if branch.status in (BranchStatus.MERGED, BranchStatus.DISCARDED):
            continue
        branch_tokens = _match_tokens(f"{branch.name} {branch.summary}")
        overlap = len(message_tokens & branch_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_branch = branch
    return best_branch


def _set_branch_status(project_state: ProjectState, branch_id: str, status: BranchStatus) -> None:
    for branch in project_state.branches:
        if branch.id == branch_id:
            branch.status = status
            return


def _match_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if token not in _MATCH_STOP_WORDS and len(token) > 2
    }


def _contains_normalized(existing: list[str], candidate: str) -> bool:
    normalized_candidate = _normalize(candidate)
    return any(_normalize(item) == normalized_candidate for item in existing)


def _has_matching_branch(
    project_state: ProjectState,
    branch_name: str,
    summary: str,
) -> bool:
    normalized_name = _normalize(branch_name)
    normalized_summary = _normalize(summary)
    return any(
        _normalize(branch.name) == normalized_name
        or _normalize(branch.summary) == normalized_summary
        for branch in project_state.branches
    )


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
