from mythinking.planning import PlannerRouter, PlanningService, format_next_actions
from mythinking.state import NextAction, NextActionDraft, PlannerAnalysis, PlanTrigger, ProjectState


def _anchored_project_state() -> ProjectState:
    return ProjectState()


def test_router_detects_no_intent_for_an_ordinary_message() -> None:
    router = PlannerRouter()

    intent = router.detect(_anchored_project_state(), "Here is more context on the idea.")

    assert intent.trigger is PlanTrigger.NONE


def test_router_detects_explicit_planning_request() -> None:
    router = PlannerRouter()

    intent = router.detect(_anchored_project_state(), "What should I do next?")

    assert intent.trigger is PlanTrigger.EXPLICIT_REQUEST
    assert intent.matched_text == "What should I do next?"


def test_service_appends_new_next_action_and_dedupes_by_normalized_description() -> None:
    service = PlanningService()
    project_state = _anchored_project_state()
    analysis = PlannerAnalysis(
        next_actions_to_add=[
            NextActionDraft(
                description="Draft the first newsletter issue",
                success_signal="Issue is written and reviewed",
                failure_signal="No draft after the time-box",
                time_box_minutes=45,
                implementation_intention="If it is Monday morning, then I will draft the issue.",
            ),
            NextActionDraft(description="  Draft the first newsletter issue  "),
        ]
    )

    updated = service.merge(project_state, analysis)

    assert len(updated.next_actions) == 1
    action = updated.next_actions[0]
    assert action.description == "Draft the first newsletter issue"
    assert action.success_signal == "Issue is written and reviewed"
    assert action.failure_signal == "No draft after the time-box"
    assert action.time_box_minutes == 45
    assert action.implementation_intention == (
        "If it is Monday morning, then I will draft the issue."
    )


def test_service_ignores_blank_descriptions() -> None:
    service = PlanningService()
    project_state = _anchored_project_state()
    analysis = PlannerAnalysis(next_actions_to_add=[NextActionDraft(description="   ")])

    updated = service.merge(project_state, analysis)

    assert updated.next_actions == []


def test_service_dedupes_against_existing_next_actions() -> None:
    service = PlanningService()
    project_state = _anchored_project_state()
    project_state.next_actions = [NextAction(description="Draft the first newsletter issue")]
    analysis = PlannerAnalysis(
        next_actions_to_add=[NextActionDraft(description="draft the first newsletter issue")]
    )

    updated = service.merge(project_state, analysis)

    assert len(updated.next_actions) == 1


def test_format_next_actions_reports_none_when_empty() -> None:
    assert format_next_actions(_anchored_project_state()) == "No next actions captured yet."


def test_format_next_actions_excludes_completed_actions() -> None:
    project_state = _anchored_project_state()
    project_state.next_actions = [
        NextAction(description="Open action", time_box_minutes=20),
        NextAction(description="Completed action", completed=True),
    ]

    rendered = format_next_actions(project_state)

    assert "Open action" in rendered
    assert "20m" in rendered
    assert "Completed action" not in rendered
