"""Deterministic next-action planning routing plus a merge/formatting service."""

from mythinking.state import NextAction, PlanIntent, PlannerAnalysis, PlanTrigger, ProjectState

_EXPLICIT_TRIGGERS = (
    "what should i do next",
    "what should we do next",
    "what's my next step",
    "whats my next step",
    "what is my next step",
    "what's the next step",
    "whats the next step",
    "what is the next step",
    "what's the next action",
    "whats the next action",
    "what is the next action",
    "plan my next step",
    "plan the next step",
    "plan next steps",
    "plan the next action",
    "help me plan next steps",
    "help me plan the next step",
    "let's plan next steps",
    "lets plan next steps",
    "give me a next action",
    "give me the next action",
    "what should the first experiment be",
    "help me plan an experiment",
    "plan the next experiment",
)


class PlannerRouter:
    """Classify a turn as an explicit request to plan the next action, or neither."""

    def detect(self, project_state: ProjectState, user_message: str) -> PlanIntent:
        lowered = _normalize(user_message)
        if not any(phrase in lowered for phrase in _EXPLICIT_TRIGGERS):
            return PlanIntent()
        return PlanIntent(trigger=PlanTrigger.EXPLICIT_REQUEST, matched_text=user_message.strip())


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
        detail = action.description
        lines.append(f"{index}. {detail} ({action.time_box_minutes}m)")
    return "\n".join(lines)


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
