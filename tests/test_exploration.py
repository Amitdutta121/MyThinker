from mythinking.exploration import (
    ConvergenceService,
    ExplorationManager,
    format_all_branch_names,
    format_branch_alternatives,
)
from mythinking.state import (
    AlternativeDraft,
    BranchStatus,
    ConvergenceOption,
    ExplorerAnalysis,
    IdeaBranch,
    NorthStar,
    ProjectState,
    SynthesizerAnalysis,
)


def _anchored_project_state() -> ProjectState:
    return ProjectState(
        north_star=NorthStar(
            problem_statement="Product idea notes are scattered",
            desired_outcome="Keep the idea thread focused",
            beneficiary="Solo founder",
        )
    )


def test_exploration_manager_appends_new_alternatives_as_active_branches() -> None:
    manager = ExplorationManager()
    project_state = _anchored_project_state()
    analysis = ExplorerAnalysis(
        alternatives_to_add=[
            AlternativeDraft(name="Newsletter", summary="Start a weekly newsletter"),
            AlternativeDraft(name="Community", summary="Start a paid community"),
        ]
    )

    updated = manager.merge(project_state, analysis)

    assert [branch.name for branch in updated.branches] == ["Newsletter", "Community"]
    assert all(branch.status is BranchStatus.ACTIVE for branch in updated.branches)


def test_exploration_manager_deduplicates_by_normalized_name_or_summary() -> None:
    manager = ExplorationManager()
    project_state = _anchored_project_state()
    project_state.branches = [IdeaBranch(name="Newsletter", summary="Start a weekly newsletter")]
    analysis = ExplorerAnalysis(
        alternatives_to_add=[
            AlternativeDraft(name="  newsletter  ", summary="Different summary"),
            AlternativeDraft(name="Community", summary="  start a weekly newsletter  "),
        ]
    )

    updated = manager.merge(project_state, analysis)

    assert len(updated.branches) == 1


def test_exploration_manager_skips_blank_names() -> None:
    manager = ExplorationManager()
    project_state = _anchored_project_state()
    analysis = ExplorerAnalysis(alternatives_to_add=[AlternativeDraft(name="   ")])

    updated = manager.merge(project_state, analysis)

    assert updated.branches == []


def test_convergence_service_marks_considered_branches_merged() -> None:
    service = ConvergenceService()
    project_state = _anchored_project_state()
    project_state.branches = [
        IdeaBranch(
            name="Newsletter Idea", summary="Start a newsletter", status=BranchStatus.ACTIVE
        ),
        IdeaBranch(name="Community Idea", summary="Start a community", status=BranchStatus.ACTIVE),
    ]
    analysis = SynthesizerAnalysis(
        options_considered=[ConvergenceOption(branch_name="Newsletter Idea")],
        recommended_choice="Start with the newsletter",
    )

    updated = service.merge(project_state, analysis)

    assert updated.branches[0].status is BranchStatus.MERGED
    assert updated.branches[1].status is BranchStatus.ACTIVE
    assert updated.north_star.current_hypothesis == "Start with the newsletter"


def test_convergence_service_ignores_unknown_branch_names() -> None:
    service = ConvergenceService()
    project_state = _anchored_project_state()
    project_state.branches = [
        IdeaBranch(name="Newsletter Idea", summary="Start a newsletter", status=BranchStatus.ACTIVE)
    ]
    analysis = SynthesizerAnalysis(
        options_considered=[ConvergenceOption(branch_name="Unrelated Branch")]
    )

    updated = service.merge(project_state, analysis)

    assert updated.branches[0].status is BranchStatus.ACTIVE


def test_format_branch_alternatives_reports_none_when_empty() -> None:
    assert format_branch_alternatives(_anchored_project_state()) == "No alternatives captured yet."


def test_format_branch_alternatives_excludes_merged_and_discarded_branches() -> None:
    project_state = _anchored_project_state()
    project_state.branches = [
        IdeaBranch(name="Active Idea", summary="Still on the table", status=BranchStatus.ACTIVE),
        IdeaBranch(name="Parked Idea", summary="Set aside for later", status=BranchStatus.PARKED),
        IdeaBranch(name="Merged Idea", summary="Already folded in", status=BranchStatus.MERGED),
        IdeaBranch(name="Discarded Idea", summary="Rejected", status=BranchStatus.DISCARDED),
    ]

    rendered = format_branch_alternatives(project_state)

    assert "Active Idea" in rendered
    assert "Parked Idea" in rendered
    assert "Merged Idea" not in rendered
    assert "Discarded Idea" not in rendered


def test_format_all_branch_names_reports_none_when_empty() -> None:
    assert format_all_branch_names(_anchored_project_state()) == "No branches captured yet."


def test_format_all_branch_names_includes_every_status() -> None:
    project_state = _anchored_project_state()
    project_state.branches = [
        IdeaBranch(name="Active Idea", status=BranchStatus.ACTIVE),
        IdeaBranch(name="Merged Idea", status=BranchStatus.MERGED),
        IdeaBranch(name="Discarded Idea", status=BranchStatus.DISCARDED),
    ]

    rendered = format_all_branch_names(project_state)

    assert "Active Idea" in rendered
    assert "Merged Idea" in rendered
    assert "Discarded Idea" in rendered
