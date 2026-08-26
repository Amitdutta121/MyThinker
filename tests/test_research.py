from mythinking.research import ResearchImporter, ResearchRouter, format_open_research_tasks
from mythinking.state import (
    EvidenceDraft,
    EvidenceKind,
    ProjectState,
    ResearcherAnalysis,
    ResearchTask,
    ResearchTaskStatus,
    ResearchTrigger,
)


def _anchored_project_state() -> ProjectState:
    return ProjectState()


def test_router_detects_no_intent_for_an_ordinary_message() -> None:
    router = ResearchRouter()

    intent = router.detect(_anchored_project_state(), "What should the first experiment be?")

    assert intent.trigger is ResearchTrigger.NONE


def test_router_detects_explicit_research_request() -> None:
    router = ResearchRouter()

    intent = router.detect(_anchored_project_state(), "Can you research this before we decide?")

    assert intent.trigger is ResearchTrigger.EXPLICIT_REQUEST
    assert intent.research_task_id == ""


def test_router_links_explicit_request_to_best_matching_open_task() -> None:
    router = ResearchRouter()
    project_state = _anchored_project_state()
    project_state.research_tasks = [
        ResearchTask(question="Does remote work reduce team collaboration?"),
        ResearchTask(question="What pricing model do competitors use?"),
    ]

    intent = router.detect(
        project_state, "Please research whether remote work reduces collaboration."
    )

    assert intent.trigger is ResearchTrigger.EXPLICIT_REQUEST
    assert intent.research_task_id == project_state.research_tasks[0].id


def test_router_ignores_answered_tasks_when_matching() -> None:
    router = ResearchRouter()
    project_state = _anchored_project_state()
    project_state.research_tasks = [
        ResearchTask(
            question="Does remote work reduce team collaboration?",
            status=ResearchTaskStatus.ANSWERED,
        )
    ]

    intent = router.detect(
        project_state, "Please research whether remote work reduces collaboration."
    )

    assert intent.trigger is ResearchTrigger.EXPLICIT_REQUEST
    assert intent.research_task_id == ""


def test_importer_appends_new_evidence_and_dedupes_by_normalized_claim() -> None:
    importer = ResearchImporter()
    project_state = _anchored_project_state()
    analysis = ResearcherAnalysis(
        findings_to_add=[
            EvidenceDraft(
                claim="The changelog shows weekly releases",
                kind=EvidenceKind.FACT,
                source_title="Internal changelog",
            ),
            EvidenceDraft(claim="  The changelog shows weekly releases  ", kind=EvidenceKind.FACT),
        ]
    )

    updated = importer.merge(project_state, "", analysis)

    assert len(updated.evidence) == 1
    assert updated.evidence[0].source_title == "Internal changelog"


def test_importer_links_new_evidence_to_the_research_task_and_resolves_it() -> None:
    importer = ResearchImporter()
    project_state = _anchored_project_state()
    task = ResearchTask(question="Does remote work reduce team collaboration?")
    project_state.research_tasks = [task]
    analysis = ResearcherAnalysis(
        findings_to_add=[
            EvidenceDraft(
                claim="An internal survey found no measurable drop in collaboration",
                kind=EvidenceKind.FACT,
                source_title="Internal survey",
            )
        ],
        task_resolved=True,
    )

    updated = importer.merge(project_state, task.id, analysis)

    updated_task = updated.research_tasks[0]
    assert updated_task.status is ResearchTaskStatus.ANSWERED
    assert updated_task.linked_evidence_ids == [updated.evidence[0].id]


def test_importer_leaves_task_open_when_not_resolved() -> None:
    importer = ResearchImporter()
    project_state = _anchored_project_state()
    task = ResearchTask(question="Does remote work reduce team collaboration?")
    project_state.research_tasks = [task]
    analysis = ResearcherAnalysis(summary="Inconclusive so far.", task_resolved=False)

    updated = importer.merge(project_state, task.id, analysis)

    assert updated.research_tasks[0].status is ResearchTaskStatus.OPEN
    assert updated.research_tasks[0].linked_evidence_ids == []


def test_importer_ignores_unknown_task_id() -> None:
    importer = ResearchImporter()
    project_state = _anchored_project_state()
    analysis = ResearcherAnalysis(
        findings_to_add=[EvidenceDraft(claim="Some finding", kind=EvidenceKind.FACT)]
    )

    updated = importer.merge(project_state, "missing-task-id", analysis)

    assert len(updated.evidence) == 1
    assert updated.research_tasks == []


def test_format_open_research_tasks_reports_none_when_empty() -> None:
    assert format_open_research_tasks(_anchored_project_state()) == "No open research tasks."


def test_format_open_research_tasks_excludes_answered_and_dropped_tasks() -> None:
    project_state = _anchored_project_state()
    project_state.research_tasks = [
        ResearchTask(question="Open question", status=ResearchTaskStatus.OPEN),
        ResearchTask(question="Answered question", status=ResearchTaskStatus.ANSWERED),
        ResearchTask(question="Dropped question", status=ResearchTaskStatus.DROPPED),
    ]

    rendered = format_open_research_tasks(project_state)

    assert "Open question" in rendered
    assert "Answered question" not in rendered
    assert "Dropped question" not in rendered
