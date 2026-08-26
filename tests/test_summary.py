from mythinking.state import (
    BranchStatus,
    Decision,
    IdeaBranch,
    NextAction,
    NorthStar,
    ProjectState,
    ResearchTask,
    ResearchTaskStatus,
    ThinkingMode,
)
from mythinking.summary import format_project_summary


def test_format_project_summary_for_freshly_started_project() -> None:
    state = ProjectState()

    summary = format_project_summary(state)

    assert f"Project: {state.project_id}" in summary
    assert "North star: not yet framed" in summary
    assert "Active branch: none (main thread)" in summary
    assert "Open questions: 0" in summary
    assert "Latest decision: none yet" in summary
    assert "Next action: not captured yet" in summary


def test_format_project_summary_reports_framing_branches_and_decisions() -> None:
    branch = IdeaBranch(name="Newsletter Idea", status=BranchStatus.ACTIVE)
    parked_branch = IdeaBranch(name="Podcast Idea", status=BranchStatus.PARKED)
    state = ProjectState(
        north_star=NorthStar(
            title="Solo founder thinking partner",
            problem_statement="Ideas scatter across notes",
            desired_outcome="One place to think clearly",
            current_hypothesis="A structured supervisor loop helps",
            next_action="Draft the M6 CLI improvements",
        ),
        current_mode=ThinkingMode.CONVERGE,
        active_branch_id=branch.id,
        branches=[branch, parked_branch],
        open_questions=["Which user segment first?"],
        research_tasks=[ResearchTask(question="Open one", status=ResearchTaskStatus.OPEN)],
        decisions=[Decision(question="Which segment?", choice="Solo founders")],
    )

    summary = format_project_summary(state)

    assert "Mode: converge" in summary
    assert "Problem: Ideas scatter across notes" in summary
    assert "Active branch: Newsletter Idea" in summary
    assert "Parked branches: Podcast Idea" in summary
    assert "Open questions: 1" in summary
    assert "Open research tasks: 1" in summary
    assert "Latest decision: Solo founders (for: Which segment?)" in summary
    assert "Next action: Draft the M6 CLI improvements" in summary


def test_format_project_summary_prefers_structured_next_action_over_free_text() -> None:
    state = ProjectState(
        north_star=NorthStar(next_action="Fallback text next action"),
        next_actions=[
            NextAction(description="Ship the resume flow", completed=True),
            NextAction(description="Write the handoff doc"),
        ],
    )

    summary = format_project_summary(state)

    assert "Next action: Write the handoff doc" in summary
