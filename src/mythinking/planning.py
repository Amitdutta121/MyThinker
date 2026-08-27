"""Next-action planning merge/formatting service."""

from mythinking.state import NextAction, PlannerAnalysis, ProjectState


class PlanningService:
    """Write Planner-generated next actions into the persisted project state."""

    def merge(self, project_state: ProjectState, analysis: PlannerAnalysis) -> ProjectState:
        project = project_state.model_copy(deep=True)
        existing = {_normalize(action.description) for action in project.next_actions}

        for draft in analysis.next_actions_to_add:
            description = draft.description.strip()
            if not description:
                continue
            key = _normalize(description)
            if key in existing:
                continue
            project.next_actions.append(
                NextAction(
                    description=description,
                    success_signal=draft.success_signal.strip(),
                    failure_signal=draft.failure_signal.strip(),
                    time_box_minutes=draft.time_box_minutes,
                    implementation_intention=draft.implementation_intention.strip(),
                )
            )
            existing.add(key)
        return project


def format_next_actions(project_state: ProjectState) -> str:
    """Render open next actions so the supervisor can reference the current plan."""

    open_actions = [action for action in project_state.next_actions if not action.completed]
    if not open_actions:
        return "No next actions captured yet."

    lines: list[str] = []
    for index, action in enumerate(open_actions, start=1):
        marker = " [stale]" if action.stale else ""
        lines.append(f"{index}. {action.description} ({action.time_box_minutes}m){marker}")
    return "\n".join(lines)


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
