"""Deterministic explore/converge routing plus merge and formatting services."""

from mythinking.state import (
    BranchStatus,
    ExplorationIntent,
    ExplorerAnalysis,
    IdeaBranch,
    IntentAction,
    ProjectState,
    SynthesizerAnalysis,
)

_EXPLORE_TRIGGERS = (
    "explore alternatives",
    "explore options",
    "explore some options",
    "explore other options",
    "give me alternatives",
    "give me some alternatives",
    "generate alternatives",
    "generate some alternatives",
    "brainstorm",
    "what are some other ways",
    "what other approaches",
    "what other options",
    "show me some options",
    "show me options",
    "other approaches",
    "different approaches",
)

_CONVERGE_TRIGGERS = (
    "help me decide",
    "help me choose",
    "help me pick",
    "which one should i",
    "which option should i",
    "let's converge",
    "lets converge",
    "converge on",
    "narrow this down",
    "narrow it down",
    "compare these options",
    "compare the options",
    "synthesize",
    "make a decision",
    "which option is best",
    "recommend one",
)


class ExplorationRouter:
    """Classify a turn as an explicit explore or converge request, or neither."""

    def detect(self, project_state: ProjectState, user_message: str) -> ExplorationIntent:
        lowered = _normalize(user_message)
        if any(phrase in lowered for phrase in _CONVERGE_TRIGGERS):
            return ExplorationIntent(
                action=IntentAction.CONVERGE, matched_text=user_message.strip()
            )
        if any(phrase in lowered for phrase in _EXPLORE_TRIGGERS):
            return ExplorationIntent(action=IntentAction.EXPLORE, matched_text=user_message.strip())
        return ExplorationIntent()


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
