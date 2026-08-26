from mythinking.exploration import (
    ConvergenceService,
    ExplorationManager,
    ExplorationRouter,
    format_branch_alternatives,
)
from mythinking.state import (
    AlternativeDraft,
    BranchStatus,
    ConvergenceOption,
    ExplorerAnalysis,
    IdeaBranch,
    IntentAction,
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


def test_router_detects_no_intent_for_an_ordinary_message() -> None:
    router = ExplorationRouter()

    intent = router.detect(_anchored_project_state(), "What should the first experiment be?")

    assert intent.action is IntentAction.NONE


def test_router_detects_explore_intent() -> None:
    router = ExplorationRouter()

    intent = router.detect(_anchored_project_state(), "Can you give me some alternatives?")

    assert intent.action is IntentAction.EXPLORE


def test_router_detects_converge_intent() -> None:
    router = ExplorationRouter()

    intent = router.detect(_anchored_project_state(), "Help me decide between these options.")

    assert intent.action is IntentAction.CONVERGE


def test_router_prefers_converge_when_both_phrasings_are_present() -> None:
    router = ExplorationRouter()

    intent = router.detect(
        _anchored_project_state(),
        "We explored options, now help me decide between them.",
    )

    assert intent.action is IntentAction.CONVERGE


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
