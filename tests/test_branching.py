from mythinking.branching import BranchSwitcher
from mythinking.state import (
    BranchCommandAction,
    BranchStatus,
    IdeaBranch,
    NorthStar,
    ProjectState,
)


def _project_with_parked_branch() -> ProjectState:
    project_state = ProjectState(
        north_star=NorthStar(
            problem_statement="Product idea notes are scattered",
            desired_outcome="Keep the idea thread focused",
            beneficiary="Solo founder",
        )
    )
    project_state.branches = [
        IdeaBranch(
            name="Newsletter Idea",
            summary="Start a newsletter for solo founders",
            status=BranchStatus.PARKED,
        )
    ]
    return project_state


def test_detect_returns_none_action_for_an_ordinary_message() -> None:
    switcher = BranchSwitcher()
    project_state = _project_with_parked_branch()

    command = switcher.detect(project_state, "What should the first experiment be?")

    assert command.action is BranchCommandAction.NONE


def test_detect_matches_an_explicit_switch_to_an_existing_branch() -> None:
    switcher = BranchSwitcher()
    project_state = _project_with_parked_branch()

    command = switcher.detect(project_state, "Let's switch to the newsletter branch.")

    assert command.action is BranchCommandAction.SWITCH
    assert command.target_branch_id == project_state.branches[0].id
    assert command.target_branch_name == "Newsletter Idea"


def test_detect_recognizes_return_to_main_goal_language() -> None:
    switcher = BranchSwitcher()
    project_state = _project_with_parked_branch()

    command = switcher.detect(project_state, "Okay, let's return to the main goal now.")

    assert command.action is BranchCommandAction.RETURN_TO_MAIN
    assert command.target_branch_id is None


def test_detect_does_not_match_switch_language_without_a_known_branch() -> None:
    switcher = BranchSwitcher()
    project_state = _project_with_parked_branch()

    command = switcher.detect(project_state, "Let's switch to a completely different idea.")

    assert command.action is BranchCommandAction.NONE


def test_apply_switch_activates_the_target_and_parks_the_previous_branch() -> None:
    switcher = BranchSwitcher()
    project_state = _project_with_parked_branch()
    project_state.branches.append(
        IdeaBranch(name="Second Idea", summary="Another tangent", status=BranchStatus.ACTIVE)
    )
    project_state.active_branch_id = project_state.branches[1].id
    command = switcher.detect(project_state, "Switch to the newsletter branch.")

    updated = switcher.apply(project_state, command)

    assert updated.active_branch_id == project_state.branches[0].id
    assert updated.branches[0].status is BranchStatus.ACTIVE
    assert updated.branches[1].status is BranchStatus.PARKED


def test_apply_return_to_main_parks_the_active_branch_and_clears_active_branch_id() -> None:
    switcher = BranchSwitcher()
    project_state = _project_with_parked_branch()
    project_state.branches[0].status = BranchStatus.ACTIVE
    project_state.active_branch_id = project_state.branches[0].id
    command = switcher.detect(project_state, "Let's return to the main goal.")

    updated = switcher.apply(project_state, command)

    assert updated.active_branch_id is None
    assert updated.branches[0].status is BranchStatus.PARKED
