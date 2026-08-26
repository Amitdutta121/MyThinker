from mythinking.evidence import EvidenceLedger, format_evidence_ledger
from mythinking.state import (
    EvidenceAnalysis,
    EvidenceDraft,
    EvidenceItem,
    EvidenceKind,
    ProjectState,
    ResearchTaskDraft,
)


def test_merge_appends_new_evidence_and_research_tasks() -> None:
    ledger = EvidenceLedger()
    project_state = ProjectState()
    analysis = EvidenceAnalysis(
        evidence_to_add=[
            EvidenceDraft(
                claim="Remote work reduces spontaneous collaboration",
                kind=EvidenceKind.HYPOTHESIS,
                notes="Stated as a universal claim without a cited source.",
            ),
            EvidenceDraft(
                claim="The team currently ships weekly",
                kind=EvidenceKind.FACT,
                source_title="Internal changelog",
            ),
        ],
        research_tasks_to_add=[
            ResearchTaskDraft(
                question="Does remote work measurably reduce collaboration for this team?",
                notes="Run a two-week trial and compare output.",
            )
        ],
    )

    updated = ledger.merge(project_state, analysis)

    assert len(updated.evidence) == 2
    assert updated.evidence[0].kind is EvidenceKind.HYPOTHESIS
    assert updated.evidence[1].kind is EvidenceKind.FACT
    assert updated.evidence[1].source_title == "Internal changelog"
    assert len(updated.research_tasks) == 1
    assert "remote work" in updated.research_tasks[0].question.lower()


def test_merge_deduplicates_by_normalized_claim_and_question() -> None:
    ledger = EvidenceLedger()
    project_state = ProjectState()
    project_state.evidence = [
        EvidenceItem(claim="The team currently ships weekly", kind=EvidenceKind.FACT)
    ]
    analysis = EvidenceAnalysis(
        evidence_to_add=[
            EvidenceDraft(claim="  The team currently ships weekly  ", kind=EvidenceKind.FACT),
        ]
    )

    updated = ledger.merge(project_state, analysis)

    assert len(updated.evidence) == 1


def test_merge_skips_blank_claims_and_questions() -> None:
    ledger = EvidenceLedger()
    project_state = ProjectState()
    analysis = EvidenceAnalysis(
        evidence_to_add=[EvidenceDraft(claim="   ", kind=EvidenceKind.FACT)],
        research_tasks_to_add=[ResearchTaskDraft(question="   ")],
    )

    updated = ledger.merge(project_state, analysis)

    assert updated.evidence == []
    assert updated.research_tasks == []


def test_format_evidence_ledger_reports_no_evidence_when_empty() -> None:
    assert format_evidence_ledger(ProjectState()) == "No evidence captured yet."


def test_format_evidence_ledger_groups_by_kind_with_citations() -> None:
    project_state = ProjectState()
    project_state.evidence = [
        EvidenceItem(
            claim="The team currently ships weekly",
            kind=EvidenceKind.FACT,
            source_title="Internal changelog",
        ),
        EvidenceItem(
            claim="A narrower beta will reduce support load",
            kind=EvidenceKind.INFERENCE,
        ),
        EvidenceItem(
            claim="Remote work always reduces innovation",
            kind=EvidenceKind.HYPOTHESIS,
        ),
    ]

    rendered = format_evidence_ledger(project_state)

    assert "Facts:" in rendered
    assert "(source: Internal changelog)" in rendered
    assert "Inferences:" in rendered
    assert "Hypotheses (unverified):" in rendered
    assert "(no source provided)" in rendered
    fact_index = rendered.index("Facts:")
    inference_index = rendered.index("Inferences:")
    hypothesis_index = rendered.index("Hypotheses")
    assert fact_index < inference_index < hypothesis_index
