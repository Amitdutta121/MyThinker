"""Scoped, per-agent context formatting -- the replacement for raw ProjectState dumps.

Below `context_retrieval_threshold` items, growable fields (evidence,
research_tasks, decisions) are rendered in full by the existing deterministic
formatters. At or above it, `ContextRetriever` uses the shared `SqliteStore`
(`retrieval.py`) to select only the top-K items relevant to the current turn,
instead of sending everything accumulated so far.
"""

from langgraph.store.sqlite import SqliteStore

from mythinking.evidence import format_evidence_ledger
from mythinking.research import format_open_research_tasks
from mythinking.retrieval import search_content
from mythinking.state import ProjectState


def format_north_star_brief(project_state: ProjectState) -> str:
    north_star = project_state.north_star
    lines = [f"Title: {north_star.title}"]
    if north_star.problem_statement:
        lines.append(f"Problem: {north_star.problem_statement}")
    if north_star.desired_outcome:
        lines.append(f"Desired outcome: {north_star.desired_outcome}")
    if north_star.beneficiary:
        lines.append(f"Beneficiary: {north_star.beneficiary}")
    if north_star.current_hypothesis:
        lines.append(f"Current hypothesis: {north_star.current_hypothesis}")
    if north_star.constraints:
        lines.append(f"Constraints: {', '.join(north_star.constraints)}")
    if north_star.success_criteria:
        lines.append(f"Success criteria: {', '.join(north_star.success_criteria)}")
    if north_star.non_goals:
        lines.append(f"Non-goals: {', '.join(north_star.non_goals)}")
    return "\n".join(lines)


def format_open_questions(project_state: ProjectState) -> str:
    if not project_state.open_questions:
        return "No open questions captured yet."
    return "\n".join(f"{i}. {q}" for i, q in enumerate(project_state.open_questions, start=1))


def format_parked_ideas(project_state: ProjectState) -> str:
    if not project_state.parked_ideas:
        return "No parked ideas."
    return "\n".join(f"{i}. {idea}" for i, idea in enumerate(project_state.parked_ideas, start=1))


def format_assumptions(project_state: ProjectState) -> str:
    if not project_state.assumptions:
        return "No assumptions captured yet."
    lines = []
    for index, assumption in enumerate(project_state.assumptions, start=1):
        lines.append(
            f"{index}. {assumption.statement} "
            f"(status: {assumption.status.value}, importance: {assumption.importance})"
        )
    return "\n".join(lines)


def format_decisions(project_state: ProjectState) -> str:
    """Render recorded decisions. Currently inert: nothing in this codebase writes to
    `ProjectState.decisions` yet, so this returns the empty sentinel today; added for
    forward-compatibility so a future decision-recording feature has a formatter ready."""

    if not project_state.decisions:
        return "No decisions recorded yet."
    lines = []
    for index, decision in enumerate(project_state.decisions, start=1):
        lines.append(f"{index}. {decision.question} -> {decision.choice}")
    return "\n".join(lines)


def format_project_context(project_state: ProjectState) -> str:
    """Compact orientation summary for the supervisor: mode, active branch, north star, open Qs."""

    active_branch = next(
        (b for b in project_state.branches if b.id == project_state.active_branch_id),
        None,
    )
    lines = [
        f"Current mode: {project_state.current_mode.value}",
        f"Active branch: {active_branch.name if active_branch else 'none (main thread)'}",
        "",
        format_north_star_brief(project_state),
        "",
        f"Open questions:\n{format_open_questions(project_state)}",
    ]
    return "\n".join(lines)


class ContextRetriever:
    """Scoped context for growable ProjectState fields: full list below threshold,
    retrieval-selected top-K at or above it."""

    def __init__(self, store: SqliteStore, *, threshold: int, top_k: int) -> None:
        self.store = store
        self.threshold = threshold
        self.top_k = top_k

    def select_evidence(self, project_state: ProjectState, query: str) -> str:
        items = project_state.evidence
        if len(items) < self.threshold:
            return format_evidence_ledger(project_state)
        results = search_content(
            self.store, project_state.project_id, "evidence", query, top_k=self.top_k
        )
        if not results:
            return format_evidence_ledger(project_state)
        lines = [f"(most relevant {len(results)} of {len(items)} evidence items)"]
        for index, result in enumerate(results, start=1):
            value = result.value
            source = value.get("source_title") or value.get("source_url") or "(no source provided)"
            lines.append(
                f"{index}. [{value.get('kind', 'fact')}] {value.get('text', '')} ({source})"
            )
        return "\n".join(lines)

    def select_research_tasks(self, project_state: ProjectState, query: str) -> str:
        items = project_state.research_tasks
        if len(items) < self.threshold:
            return format_open_research_tasks(project_state)
        results = search_content(
            self.store, project_state.project_id, "research_task", query, top_k=self.top_k
        )
        if not results:
            return format_open_research_tasks(project_state)
        lines = [f"(most relevant {len(results)} of {len(items)} research tasks)"]
        for index, result in enumerate(results, start=1):
            value = result.value
            lines.append(f"{index}. {value.get('text', '')}: {value.get('notes', '')}")
        return "\n".join(lines)

    def select_decisions(self, project_state: ProjectState, query: str) -> str:
        items = project_state.decisions
        if len(items) < self.threshold:
            return format_decisions(project_state)
        results = search_content(
            self.store, project_state.project_id, "decision", query, top_k=self.top_k
        )
        if not results:
            return format_decisions(project_state)
        lines = [f"(most relevant {len(results)} of {len(items)} decisions)"]
        for index, result in enumerate(results, start=1):
            value = result.value
            lines.append(f"{index}. {value.get('text', '')} -> {value.get('choice', '')}")
        return "\n".join(lines)

    def select_document_chunks(
        self, project_id: str, query: str, *, top_k: int | None = None
    ) -> str:
        results = search_content(
            self.store, project_id, "document_chunk", query, top_k=top_k or self.top_k
        )
        if not results:
            return "No research sources retrieved yet."
        lines = []
        for index, result in enumerate(results, start=1):
            value = result.value
            lines.append(f"{index}. {value.get('text', '')}")
        return "\n\n".join(lines)


__all__ = [
    "ContextRetriever",
    "format_assumptions",
    "format_decisions",
    "format_north_star_brief",
    "format_open_questions",
    "format_parked_ideas",
    "format_project_context",
]
