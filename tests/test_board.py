"""Deterministic board helpers: plan staleness and the proposal-commit routine."""

from mythinking.board import commit_proposal, mark_plan_stale
from mythinking.state import (
    BranchStatus,
    DirectionProposal,
    IdeaBranch,
    NextAction,
    NorthStar,
    ProjectState,
)


def _state_with_plan() -> ProjectState:
    return ProjectState(
        north_star=NorthStar(title="Note app", problem_statement="Notes get lost"),
        next_actions=[
            NextAction(description="Agent step", origin="agent"),
            NextAction(description="My own step", origin="user"),
            NextAction(description="Already done", origin="agent", completed=True),
        ],
    )


def test_mark_plan_stale_skips_completed_and_user_steps() -> None:
    state = _state_with_plan()

    mark_plan_stale(state)

    by_desc = {a.description: a for a in state.next_actions}
    assert by_desc["Agent step"].stale is True
    assert by_desc["My own step"].stale is False
    assert by_desc["Already done"].stale is False


def test_commit_proposal_sets_direction_logs_decision_and_clears_proposal() -> None:
    state = _state_with_plan()
    state.proposal = DirectionProposal(
        statement="Ship the local-first app",
        rationale="fewest unknowns",
        alternatives_considered=["clipper first", "both at once"],
    )

    committed = commit_proposal(state)

    assert committed.north_star.current_hypothesis == "Ship the local-first app"
    assert committed.proposal is None
    assert len(committed.decisions) == 1
    decision = committed.decisions[0]
    assert decision.question == "Committed project direction"
    assert decision.choice == "Ship the local-first app"
    assert decision.alternatives == ["clipper first", "both at once"]
    # The direction changed, so the agent plan is stale but the user step is not.
    by_desc = {a.description: a for a in committed.next_actions}
    assert by_desc["Agent step"].stale is True
    assert by_desc["My own step"].stale is False
    # The source state is untouched (commit returns a fresh copy).
    assert state.proposal is not None
    assert state.north_star.current_hypothesis == ""


def test_commit_proposal_merges_a_matching_active_branch() -> None:
    state = ProjectState(
        north_star=NorthStar(title="x", problem_statement="y"),
        branches=[
            IdeaBranch(name="Local-first app", status=BranchStatus.ACTIVE),
            IdeaBranch(name="Browser clipper", status=BranchStatus.PARKED),
        ],
        proposal=DirectionProposal(statement="Build the Local-first app now"),
    )

    committed = commit_proposal(state)

    by_name = {b.name: b for b in committed.branches}
    assert by_name["Local-first app"].status == BranchStatus.MERGED
    assert by_name["Browser clipper"].status == BranchStatus.PARKED


def test_commit_proposal_leaves_plan_when_direction_is_unchanged() -> None:
    state = ProjectState(
        north_star=NorthStar(title="x", problem_statement="y", current_hypothesis="Same direction"),
        next_actions=[NextAction(description="Agent step", origin="agent")],
        proposal=DirectionProposal(statement="Same direction"),
    )

    committed = commit_proposal(state)

    assert committed.next_actions[0].stale is False
