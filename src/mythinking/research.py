"""Research-task matching plus an evidence-import pipeline for scoped findings."""

import re

from mythinking.state import (
    EvidenceItem,
    ProjectState,
    ResearcherAnalysis,
    ResearchTask,
    ResearchTaskStatus,
)

_MATCH_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "dig",
    "find",
    "for",
    "from",
    "go",
    "in",
    "into",
    "investigate",
    "is",
    "it",
    "let",
    "lets",
    "look",
    "more",
    "of",
    "on",
    "or",
    "our",
    "out",
    "please",
    "research",
    "researching",
    "start",
    "that",
    "the",
    "this",
    "to",
    "up",
    "we",
    "with",
    "you",
    "your",
}


class ResearchImporter:
    """Write Researcher findings into the evidence ledger and resolve the linked task."""

    def merge(
        self,
        project_state: ProjectState,
        research_task_id: str,
        analysis: ResearcherAnalysis,
    ) -> ProjectState:
        project = project_state.model_copy(deep=True)

        existing_claims = {_normalize(item.claim) for item in project.evidence}
        new_evidence_ids: list[str] = []
        for draft in analysis.findings_to_add:
            key = _normalize(draft.claim)
            if not key or key in existing_claims:
                continue
            item = EvidenceItem(
                claim=draft.claim.strip(),
                kind=draft.kind,
                source_url=draft.source_url.strip(),
                source_title=draft.source_title.strip(),
                notes=draft.notes.strip(),
            )
            project.evidence.append(item)
            existing_claims.add(key)
            new_evidence_ids.append(item.id)

        task = _find_task(project, research_task_id)
        if task is not None:
            if new_evidence_ids:
                task.linked_evidence_ids = _append_unique_ids(
                    task.linked_evidence_ids, new_evidence_ids
                )
            if analysis.task_resolved:
                task.status = ResearchTaskStatus.ANSWERED

        return project


def format_open_research_tasks(project_state: ProjectState) -> str:
    """Render open research tasks so the supervisor can traceably recommend research."""

    open_tasks = [
        task for task in project_state.research_tasks if task.status is ResearchTaskStatus.OPEN
    ]
    if not open_tasks:
        return "No open research tasks."

    lines: list[str] = []
    for index, task in enumerate(open_tasks, start=1):
        detail = task.notes.strip() or "No notes captured."
        lines.append(f"{index}. {task.question}: {detail}")
    return "\n".join(lines)


def _find_task(project_state: ProjectState, research_task_id: str) -> ResearchTask | None:
    if not research_task_id:
        return None
    for task in project_state.research_tasks:
        if task.id == research_task_id:
            return task
    return None


def best_matching_open_task(project_state: ProjectState, user_message: str) -> ResearchTask | None:
    """Pick the open research task whose question shares the most tokens with the message."""

    message_tokens = _match_tokens(user_message)
    if not message_tokens:
        return None
    best_task: ResearchTask | None = None
    best_overlap = 0
    for task in project_state.research_tasks:
        if task.status is not ResearchTaskStatus.OPEN:
            continue
        task_tokens = _match_tokens(task.question)
        overlap = len(message_tokens & task_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_task = task
    return best_task


def _append_unique_ids(existing: list[str], additions: list[str]) -> list[str]:
    merged = list(existing)
    seen = set(merged)
    for item in additions:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def _match_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if token not in _MATCH_STOP_WORDS and len(token) > 2
    }


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
