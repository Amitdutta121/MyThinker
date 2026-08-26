"""Merge extracted evidence into project state and render it for citation."""

from mythinking.state import (
    EvidenceAnalysis,
    EvidenceItem,
    EvidenceKind,
    ProjectState,
    ResearchTask,
)

_KIND_LABELS = {
    EvidenceKind.FACT: "Facts",
    EvidenceKind.INFERENCE: "Inferences",
    EvidenceKind.HYPOTHESIS: "Hypotheses (unverified)",
}

_KIND_ORDER = (EvidenceKind.FACT, EvidenceKind.INFERENCE, EvidenceKind.HYPOTHESIS)


class EvidenceLedger:
    """Write evidence-extraction updates into the persisted project state."""

    def merge(self, project_state: ProjectState, analysis: EvidenceAnalysis) -> ProjectState:
        project = project_state.model_copy(deep=True)

        existing_claims = {_normalize(item.claim) for item in project.evidence}
        for draft in analysis.evidence_to_add:
            key = _normalize(draft.claim)
            if not key or key in existing_claims:
                continue
            project.evidence.append(
                EvidenceItem(
                    claim=draft.claim.strip(),
                    kind=draft.kind,
                    source_url=draft.source_url.strip(),
                    source_title=draft.source_title.strip(),
                    notes=draft.notes.strip(),
                )
            )
            existing_claims.add(key)

        existing_questions = {_normalize(task.question) for task in project.research_tasks}
        for draft in analysis.research_tasks_to_add:
            key = _normalize(draft.question)
            if not key or key in existing_questions:
                continue
            project.research_tasks.append(
                ResearchTask(question=draft.question.strip(), notes=draft.notes.strip())
            )
            existing_questions.add(key)

        return project


def format_evidence_ledger(project_state: ProjectState) -> str:
    """Render the evidence ledger grouped by kind with an inline citation per item."""

    if not project_state.evidence:
        return "No evidence captured yet."

    grouped: dict[EvidenceKind, list[EvidenceItem]] = {kind: [] for kind in _KIND_ORDER}
    for item in project_state.evidence:
        grouped[item.kind].append(item)

    sections: list[str] = []
    for kind in _KIND_ORDER:
        items = grouped[kind]
        if not items:
            continue
        lines = [f"{_KIND_LABELS[kind]}:"]
        for index, item in enumerate(items, start=1):
            lines.append(f"  {index}. {item.claim}{_citation_suffix(item)}")
        sections.append("\n".join(lines))
    return "\n".join(sections)


def _citation_suffix(item: EvidenceItem) -> str:
    source = item.source_title.strip() or item.source_url.strip()
    if source:
        return f" (source: {source})"
    return " (no source provided)"


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
