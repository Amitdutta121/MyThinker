"""Preserve detected tangents without letting them disappear from project state."""

from mythinking.state import (
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
