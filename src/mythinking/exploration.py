"""Explore/converge merge and formatting services."""

from mythinking.state import (
    BranchStatus,
    ExplorerAnalysis,
    IdeaBranch,
    ProjectState,
    SynthesizerAnalysis,
)


class ExplorationManager:
    """Write Explorer-generated alternatives into the persisted project state."""

    def merge(self, project_state: ProjectState, analysis: ExplorerAnalysis) -> ProjectState:
        project = project_state.model_copy(deep=True)
        existing = {_normalize(branch.name) for branch in project.branches}
        existing |= {_normalize(branch.summary) for branch in project.branches if branch.summary}

        for draft in analysis.alternatives_to_add:
            name = draft.name.strip()
            if not name:
                continue
            key_name = _normalize(name)
            key_summary = _normalize(draft.summary)
            if key_name in existing or (key_summary and key_summary in existing):
                continue
            project.branches.append(
                IdeaBranch(
                    name=name,
                    summary=draft.summary.strip(),
                    relationship_to_goal=draft.relationship_to_goal.strip(),
                    status=BranchStatus.ACTIVE,
                )
            )
            existing.add(key_name)
            if key_summary:
                existing.add(key_summary)
        return project


class ConvergenceService:
    """Fold Synthesizer output into the persisted project state."""

    def merge(self, project_state: ProjectState, analysis: SynthesizerAnalysis) -> ProjectState:
        project = project_state.model_copy(deep=True)
        for option in analysis.options_considered:
            branch = _find_branch_by_name(project, option.branch_name)
            if branch is not None:
                branch.status = BranchStatus.MERGED
        if analysis.recommended_choice.strip():
            project.north_star.current_hypothesis = analysis.recommended_choice.strip()
        return project


def format_branch_alternatives(project_state: ProjectState) -> str:
    """Render the alternatives currently on the table, excluding merged/discarded ones."""

    open_branches = [
        branch
        for branch in project_state.branches
        if branch.status in (BranchStatus.ACTIVE, BranchStatus.PARKED)
    ]
    if not open_branches:
        return "No alternatives captured yet."

    lines: list[str] = []
    for index, branch in enumerate(open_branches, start=1):
        detail = branch.summary or "No summary captured."
        status_label = "parked" if branch.status is BranchStatus.PARKED else "active"
        lines.append(f"{index}. {branch.name} ({status_label}): {detail}")
    return "\n".join(lines)


def format_all_branch_names(project_state: ProjectState) -> str:
    """Every branch name regardless of status, for exact-name matching against project_state.

    Distinct from `format_branch_alternatives`, which excludes merged/discarded
    branches -- some prompts (explorer, synthesizer) must avoid repeating *any*
    existing branch name, not just the still-open ones.
    """

    if not project_state.branches:
        return "No branches captured yet."
    return "\n".join(f"{branch.name} ({branch.status.value})" for branch in project_state.branches)


def _find_branch_by_name(project_state: ProjectState, name: str) -> IdeaBranch | None:
    target = _normalize(name)
    if not target:
        return None
    for branch in project_state.branches:
        if _normalize(branch.name) == target:
            return branch
    return None


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
