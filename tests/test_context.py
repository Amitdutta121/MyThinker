from dataclasses import dataclass, field
from typing import Any

from mythinking.context import (
    ContextRetriever,
    format_assumptions,
    format_decisions,
    format_north_star_brief,
    format_open_questions,
    format_parked_ideas,
    format_project_context,
)
from mythinking.state import (
    Assumption,
    Decision,
    EvidenceItem,
    EvidenceKind,
    IdeaBranch,
    NorthStar,
    ProjectState,
    ResearchTask,
)


def _project_state(**overrides: Any) -> ProjectState:
    defaults: dict[str, Any] = {
        "north_star": NorthStar(title="Untitled idea"),
    }
    defaults.update(overrides)
    return ProjectState(**defaults)


def test_format_north_star_brief_includes_populated_fields_only() -> None:
    project_state = _project_state(
        north_star=NorthStar(title="Focus app", problem_statement="Too many tabs")
    )

    rendered = format_north_star_brief(project_state)

    assert "Focus app" in rendered
    assert "Too many tabs" in rendered
    assert "Beneficiary" not in rendered


def test_format_open_questions_reports_none_when_empty() -> None:
    assert format_open_questions(_project_state()) == "No open questions captured yet."


def test_format_open_questions_numbers_entries() -> None:
    project_state = _project_state(open_questions=["What's the MVP?", "Who pays for this?"])

    rendered = format_open_questions(project_state)

    assert "1. What's the MVP?" in rendered
    assert "2. Who pays for this?" in rendered


def test_format_parked_ideas_reports_none_when_empty() -> None:
    assert format_parked_ideas(_project_state()) == "No parked ideas."


def test_format_assumptions_reports_none_when_empty() -> None:
    assert format_assumptions(_project_state()) == "No assumptions captured yet."


def test_format_assumptions_includes_status_and_importance() -> None:
    project_state = _project_state(
        assumptions=[Assumption(statement="Users want this", importance=5)]
    )

    rendered = format_assumptions(project_state)

    assert "Users want this" in rendered
    assert "importance: 5" in rendered


def test_format_decisions_reports_none_when_empty() -> None:
    assert format_decisions(_project_state()) == "No decisions recorded yet."


def test_format_decisions_renders_recorded_decisions() -> None:
    project_state = _project_state(
        decisions=[Decision(question="Which channel?", choice="Newsletter")]
    )

    rendered = format_decisions(project_state)

    assert "Which channel?" in rendered
    assert "Newsletter" in rendered


def test_format_project_context_includes_mode_and_active_branch() -> None:
    branch = IdeaBranch(name="Newsletter track")
    project_state = _project_state(
        branches=[branch],
        active_branch_id=branch.id,
        open_questions=["What's next?"],
    )

    rendered = format_project_context(project_state)

    assert "Newsletter track" in rendered
    assert "capture" in rendered  # default current_mode
    assert "What's next?" in rendered


def test_format_project_context_reports_no_active_branch() -> None:
    rendered = format_project_context(_project_state())

    assert "none (main thread)" in rendered


@dataclass
class _FakeSearchItem:
    key: str
    value: dict[str, Any]


@dataclass
class _FakeStore:
    """Stands in for SqliteStore.search -- ContextRetriever only calls .search()."""

    results: list[_FakeSearchItem] = field(default_factory=list)
    calls: list[tuple] = field(default_factory=list)

    def search(self, namespace, *, query=None, filter=None, limit=10, offset=0):
        self.calls.append((namespace, query, limit))
        return self.results


def test_context_retriever_uses_full_formatter_below_threshold() -> None:
    project_state = _project_state(
        evidence=[EvidenceItem(claim="Users churn early", kind=EvidenceKind.FACT)]
    )
    store = _FakeStore(results=[_FakeSearchItem("should-not-be-used", {"text": "unused"})])
    retriever = ContextRetriever(store, threshold=5, top_k=3)

    rendered = retriever.select_evidence(project_state, "why do users churn")

    assert "Users churn early" in rendered
    assert store.calls == []  # never queried the store below threshold


def test_context_retriever_uses_search_results_at_threshold() -> None:
    evidence = [EvidenceItem(claim=f"claim {i}", kind=EvidenceKind.FACT) for i in range(5)]
    project_state = _project_state(evidence=evidence)
    store = _FakeStore(
        results=[_FakeSearchItem("ev1", {"text": "most relevant claim", "kind": "fact"})]
    )
    retriever = ContextRetriever(store, threshold=5, top_k=3)

    rendered = retriever.select_evidence(project_state, "which claim matters")

    assert "most relevant claim" in rendered
    assert "most relevant 1 of 5" in rendered
    assert len(store.calls) == 1


def test_context_retriever_falls_back_to_full_formatter_when_search_returns_nothing() -> None:
    evidence = [EvidenceItem(claim=f"claim {i}", kind=EvidenceKind.FACT) for i in range(5)]
    project_state = _project_state(evidence=evidence)
    store = _FakeStore(results=[])
    retriever = ContextRetriever(store, threshold=5, top_k=3)

    rendered = retriever.select_evidence(project_state, "irrelevant query")

    assert "claim 0" in rendered


def test_context_retriever_select_research_tasks_below_threshold() -> None:
    project_state = _project_state(
        research_tasks=[ResearchTask(question="Is there demand?", notes="ask users")]
    )
    store = _FakeStore()
    retriever = ContextRetriever(store, threshold=5, top_k=3)

    rendered = retriever.select_research_tasks(project_state, "demand")

    assert "Is there demand?" in rendered
    assert store.calls == []


def test_context_retriever_select_document_chunks_reports_none_when_empty() -> None:
    store = _FakeStore(results=[])
    retriever = ContextRetriever(store, threshold=5, top_k=3)

    rendered = retriever.select_document_chunks("proj1", "query")

    assert rendered == "No research sources retrieved yet."


def test_context_retriever_select_document_chunks_prefixes_page_citation_tags() -> None:
    store = _FakeStore(
        results=[
            _FakeSearchItem(
                "c1",
                {"text": "Vitamin D matters.", "page": 3, "document_title": "health.pdf"},
            ),
            _FakeSearchItem(
                "c2",
                {"text": "A blog claim.", "document_title": "Example Blog"},
            ),
        ]
    )
    retriever = ContextRetriever(store, threshold=5, top_k=3)

    rendered = retriever.select_document_chunks("proj1", "vitamin d")

    assert "[[health.pdf p.3]]\nVitamin D matters." in rendered
    assert "[[Example Blog]]\nA blog claim." in rendered
