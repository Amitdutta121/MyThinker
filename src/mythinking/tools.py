"""Tools for the agentic Researcher and Supervisor.

No manual gate decides which of these are visible to a model at any given
moment (besides `enable_deep_research` deciding whether `run_deep_research`
is even in the list at all -- see its docstring below). Tool *selection*
within whatever list is handed to `create_agent` is the model's own
judgment, guided by each tool's description -- the idiomatic LangChain
pattern, not a hand-coded keyword check.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain_core.tools import BaseTool, tool
from langgraph.store.sqlite import SqliteStore
from pypdf import PdfReader
from tavily import TavilyClient

from mythinking.agents.evidence_analyst import EvidenceAnalyst
from mythinking.agents.explorer import Explorer
from mythinking.agents.frame_analyst import FrameAnalyst
from mythinking.agents.planner import Planner
from mythinking.agents.synthesizer import Synthesizer
from mythinking.board import MutableStateHolder, apply_frame_analysis, mark_plan_stale
from mythinking.config import Settings
from mythinking.context import ContextRetriever
from mythinking.deep_research import DeepResearchRunner, ResearchSource
from mythinking.documents import Document, DocumentChunk, chunk_text
from mythinking.exploration import ExplorationManager, format_branch_alternatives
from mythinking.gates import (
    check_evidence,
    check_north_star_proposal,
    check_user_decision,
    user_authorized_commitment,
)
from mythinking.planning import PlanningService, format_next_actions
from mythinking.research import format_open_research_tasks
from mythinking.retrieval import index_chunk, index_document, list_documents
from mythinking.state import (
    BranchStatus,
    Decision,
    DirectionProposal,
    EvidenceItem,
    EvidenceKind,
    ProjectState,
)

_FETCH_TIMEOUT_SECONDS = 15.0
_MAX_RESULT_CHARS = 4000
_PARK_PHRASES = (
    "park",
    "set aside",
    "set it aside",
    "save for later",
    "shelve",
    "table it",
    "table ",
)


@dataclass
class ThinkingToolDeps:
    """Pre-built domain engines + a gate model, injected by the runtime (fakeable in tests)."""

    frame_analyst: FrameAnalyst
    explorer: Explorer
    synthesizer: Synthesizer
    planner: Planner
    evidence_analyst: EvidenceAnalyst
    gate_model: Any
    exploration_manager: ExplorationManager | None = None
    planning_service: PlanningService | None = None


def build_research_tools(
    project_id: str,
    store: SqliteStore,
    settings: Settings,
    research_task_id: str = "",
    *,
    deep_research_runner: DeepResearchRunner | None = None,
) -> list[BaseTool]:
    """Build this turn's research toolset, closing over the current project/store."""

    runner = deep_research_runner or DeepResearchRunner(settings)

    @tool
    def web_search(query: str) -> str:
        """Search the web for one specific, narrower fact or source.

        Cheaper and faster than run_deep_research -- use this for a
        targeted lookup (e.g. one fact, one comparison), not a
        comprehensive multi-source report.
        """
        results = _run_web_search(query, settings)
        _store_and_index_sources(project_id, store, research_task_id, results)
        return _summarize_sources_for_model(results)

    @tool
    def fetch_url(url: str) -> str:
        """Fetch and read one specific web page's text content.

        Use this for a URL the user pasted, or one found via web_search.
        """
        source = _fetch_page(url)
        _store_and_index_sources(project_id, store, research_task_id, [source])
        return source.content[:_MAX_RESULT_CHARS] or "The page returned no readable text."

    @tool
    def run_deep_research(query: str) -> str:
        """Run a thorough, multi-source live web-research pass.

        Expensive and slow. Only call this when the user has explicitly and
        unambiguously asked for deep, thorough, or extensive research (e.g.
        "do a deep research on this", "search the web thoroughly for X").
        For a narrower question, prefer web_search or fetch_url, or answer
        directly if you already have enough information.
        """
        sources = runner.run(query)
        _store_and_index_sources(project_id, store, research_task_id, sources)
        return _summarize_sources_for_model(sources)

    tools: list[BaseTool] = [web_search, fetch_url]
    if settings.enable_deep_research:
        tools.append(run_deep_research)
    return tools


def build_context_tools(
    holder: MutableStateHolder,
    context_retriever: ContextRetriever,
) -> list[BaseTool]:
    """Read-only lookups over this project's own saved state. No internet access.

    Each closure reads `holder.project_state` at call time, so it reflects any
    mutations made earlier in the same turn.
    """

    @tool
    def get_project_snapshot() -> str:
        """Read the full authoritative project state as JSON. Read-only.

        Use when you need detail beyond the compact status block: exact branch
        list, assumptions, decisions, the current proposal, or the plan.
        """
        return holder.project_state.model_dump_json(indent=2)

    @tool
    def get_evidence_ledger(topic: str = "") -> str:
        """Look up facts, inferences, and hypotheses already saved for this project.

        Pass a short topic/question describing what you're looking for.
        """
        state = holder.project_state
        query = topic or state.north_star.title
        return context_retriever.select_evidence(state, query)

    @tool
    def get_open_research_tasks() -> str:
        """List this project's open research questions that haven't been answered yet."""
        return format_open_research_tasks(holder.project_state)

    @tool
    def get_branch_alternatives() -> str:
        """List the alternative directions currently on the table for this project."""
        return format_branch_alternatives(holder.project_state)

    @tool
    def get_next_actions_plan() -> str:
        """List the next actions already planned for this project, if any."""
        return format_next_actions(holder.project_state)

    return [
        get_project_snapshot,
        get_evidence_ledger,
        get_open_research_tasks,
        get_branch_alternatives,
        get_next_actions_plan,
    ]


def _north_star_established(state: ProjectState) -> bool:
    return bool(state.north_star.problem_statement.strip())


def _require_north_star(state: ProjectState, operation: str) -> str | None:
    if _north_star_established(state):
        return None
    return (
        f"BLOCKED: {operation} requires an established North Star. If the user clearly "
        "stated their goal this turn, call set_north_star first; otherwise ask what they "
        "are trying to achieve."
    )


def build_thinking_tools(
    holder: MutableStateHolder,
    user_message: str,
    *,
    deps: ThinkingToolDeps,
    context_retriever: ContextRetriever,
    store: SqliteStore | None = None,
    settings: Settings | None = None,
) -> list[BaseTool]:
    """State-changing thinking tools + document tools, each guarded by deterministic
    preconditions under `holder.lock`. A blocked precondition returns a ``BLOCKED: ...``
    string and mutates nothing."""

    exploration_manager = deps.exploration_manager or ExplorationManager()
    planning_service = deps.planning_service or PlanningService()

    @tool
    def set_north_star(goal: str) -> str:
        """Establish the project's main goal.

        Use only when no North Star exists yet and the current user message clearly
        states what they are trying to achieve. Never invent a goal from an ambiguous
        request.
        """
        with holder.lock:
            goal = goal.strip()
            if not goal:
                return "BLOCKED: North Star cannot be empty."
            state = holder.project_state
            if _north_star_established(state):
                return (
                    "BLOCKED: a North Star already exists. Keep using the existing project "
                    "goal unless the product later adds an explicit reframe operation."
                )
            gate = check_north_star_proposal(deps.gate_model, user_message, goal)
            if not gate.supported:
                return f"BLOCKED: proposed North Star is not supported by this turn. {gate.reason}"

            normalized = (gate.normalized_goal or goal).strip()
            new_state = state.model_copy(deep=True)
            new_state.north_star.problem_statement = normalized
            title = new_state.north_star.title.strip()
            if not title or title == "Untitled idea":
                new_state.north_star.title = normalized[:80]
            frame = deps.frame_analyst.analyze(new_state, user_message)
            new_state = apply_frame_analysis(new_state, frame)
            new_state.north_star.problem_statement = (
                new_state.north_star.problem_statement or normalized
            )
            new_state.mark_updated()
            holder.project_state = new_state
            return f"North Star established: {new_state.north_star.problem_statement}"

    @tool
    def explore_ideas(question: str) -> str:
        """Generate divergent alternatives for the established project.

        Requires a North Star. Adds idea branches and open questions only -- never
        ranks, selects, commits, or plans.
        """
        with holder.lock:
            blocked = _require_north_star(holder.project_state, "exploration")
            if blocked:
                return blocked
            analysis = deps.explorer.analyze(holder.project_state, question)
            before = len(holder.project_state.branches)
            holder.project_state = exploration_manager.merge(holder.project_state, analysis)
            holder.project_state.mark_updated()
            added = [b.name for b in holder.project_state.branches[before:]]
            return json.dumps({"summary": analysis.summary, "added_branches": added}, indent=2)

    @tool
    def converge_ideas(criteria: str = "") -> str:
        """Compare active alternatives and store an AI recommendation as a PROPOSAL.

        Requires a North Star and at least two active branches. This NEVER commits the
        recommendation -- it only writes `proposal`. A separate explicit user
        authorization is required to commit.
        """
        with holder.lock:
            state = holder.project_state
            blocked = _require_north_star(state, "convergence")
            if blocked:
                return blocked
            active = [b for b in state.branches if b.status == BranchStatus.ACTIVE]
            if len(active) < 2:
                return (
                    "BLOCKED: convergence requires at least two active alternatives. "
                    "Explore first, or ask the user for alternatives."
                )
            analysis = deps.synthesizer.analyze(state, criteria)
            if not analysis.recommended_choice.strip():
                return "BLOCKED: could not produce a decision-ready recommendation."
            new_state = state.model_copy(deep=True)
            new_state.proposal = DirectionProposal(
                statement=analysis.recommended_choice.strip(),
                rationale=analysis.rationale.strip(),
                alternatives_considered=[o.branch_name for o in analysis.options_considered],
            )
            new_state.mark_updated()
            holder.project_state = new_state
            return new_state.proposal.model_dump_json(indent=2)

    @tool
    def commit_proposed_direction() -> str:
        """Commit the EXACT current proposal as the project's direction.

        Takes no argument, so no new direction can be invented here. Use only when the
        current user turn explicitly accepts the proposal or explicitly delegates the
        choice. Marks any unfinished plan stale.
        """
        with holder.lock:
            state = holder.project_state
            if state.proposal is None:
                return "BLOCKED: there is no current proposal to commit."
            if not user_authorized_commitment(user_message):
                return (
                    "BLOCKED: this turn does not explicitly authorize committing the "
                    "proposal. Present it and ask the user to confirm."
                )
            new_state = state.model_copy(deep=True)
            proposal = new_state.proposal
            old_direction = new_state.north_star.current_hypothesis
            new_state.north_star.current_hypothesis = proposal.statement
            new_state.decisions.append(
                Decision(
                    question="Committed project direction",
                    choice=proposal.statement,
                    rationale=proposal.rationale,
                    alternatives=proposal.alternatives_considered,
                )
            )
            new_state.proposal = None
            if old_direction != new_state.north_star.current_hypothesis:
                mark_plan_stale(new_state)
            lowered = new_state.north_star.current_hypothesis.lower()
            for branch in new_state.branches:
                if branch.status != BranchStatus.ACTIVE:
                    continue
                summary = branch.summary.lower()
                if branch.name.lower() in lowered or (summary and summary in lowered):
                    branch.status = BranchStatus.MERGED
            new_state.mark_updated()
            holder.project_state = new_state
            return f"Committed direction: {new_state.north_star.current_hypothesis}"

    @tool
    def record_user_decision(statement: str, rationale: str = "") -> str:
        """Record an explicit non-direction project decision made in the current turn.

        Verifies the statement is actually supported by the user's current message.
        Do not use for assistant-only recommendations. Marks any unfinished plan stale.
        """
        with holder.lock:
            statement = statement.strip()
            if not statement:
                return "BLOCKED: decision statement cannot be empty."
            gate = check_user_decision(deps.gate_model, user_message, statement)
            if not gate.supported_by_user_message:
                return f"BLOCKED: decision not supported by the current turn. {gate.reason}"
            new_state = holder.project_state.model_copy(deep=True)
            new_state.decisions.append(
                Decision(
                    question="Recorded decision",
                    choice=statement,
                    rationale=rationale.strip() or gate.reason,
                )
            )
            mark_plan_stale(new_state)
            new_state.mark_updated()
            holder.project_state = new_state
            return f"Decision recorded: {statement}"

    @tool
    def create_or_revise_plan(request: str = "") -> str:
        """Create or revise the project plan from the committed direction.

        Requires a North Star AND a committed direction (`current_hypothesis`). Never
        plans from an uncommitted proposal. Drops stale steps and adds fresh ones.
        """
        with holder.lock:
            state = holder.project_state
            blocked = _require_north_star(state, "planning")
            if blocked:
                return blocked
            if not state.north_star.current_hypothesis.strip():
                return (
                    "BLOCKED: no committed direction exists. Converge and get the user to "
                    "accept a direction before planning."
                )
            analysis = deps.planner.analyze(state, request or "Create the next concrete V1 plan.")
            new_state = state.model_copy(deep=True)
            new_state.next_actions = [a for a in new_state.next_actions if not a.stale]
            new_state = planning_service.merge(new_state, analysis)
            new_state.mark_updated()
            holder.project_state = new_state
            return json.dumps(
                {
                    "summary": analysis.summary,
                    "steps": [a.description for a in new_state.next_actions if not a.completed],
                },
                indent=2,
            )

    @tool
    def park_branch(branch_name: str, reason: str = "") -> str:
        """Park an existing idea branch for later without deleting it.

        Use only when the user explicitly asks to park/shelve/set aside a branch.
        """
        with holder.lock:
            if not any(phrase in user_message.lower() for phrase in _PARK_PHRASES):
                return "BLOCKED: the current turn did not ask to park/set aside a branch."
            target = branch_name.lower().strip()
            new_state = holder.project_state.model_copy(deep=True)
            for branch in new_state.branches:
                if branch.name.lower() == target or (target and target in branch.summary.lower()):
                    branch.status = BranchStatus.PARKED
                    if branch.summary and branch.summary not in new_state.parked_ideas:
                        new_state.parked_ideas.append(branch.summary)
                    new_state.mark_updated()
                    holder.project_state = new_state
                    return f"Parked {branch.name}. Reason: {reason or '(not supplied)'}"
            return f"No matching branch found for: {branch_name}"

    @tool
    def save_evidence(claim: str, source: str, source_excerpt: str) -> str:
        """Promote a sourced claim into project evidence.

        Pass the claim, an exact source URL/citation, and the exact supporting excerpt
        from a source tool. The claim must materially inform the established project.
        Validated for both source support and project relevance before saving.
        """
        with holder.lock:
            state = holder.project_state
            blocked = _require_north_star(state, "saving evidence")
            if blocked:
                return blocked
            claim, source, source_excerpt = claim.strip(), source.strip(), source_excerpt.strip()
            if not claim or not source or not source_excerpt:
                return "BLOCKED: claim, source, and source_excerpt are all required."
            if any(e.claim.lower() == claim.lower() for e in state.evidence):
                return "Evidence already exists."
            gate = check_evidence(
                deps.gate_model,
                state.north_star.problem_statement,
                state.north_star.current_hypothesis,
                claim,
                source_excerpt,
            )
            if not gate.supported_by_excerpt:
                return f"BLOCKED: source excerpt does not support the claim. {gate.support_reason}"
            if not gate.project_relevant:
                return (
                    "BLOCKED: claim is not materially relevant to this project. "
                    f"{gate.relevance_reason}"
                )
            is_url = source.lower().startswith(("http://", "https://"))
            new_state = state.model_copy(deep=True)
            new_state.evidence.append(
                EvidenceItem(
                    claim=claim,
                    kind=EvidenceKind.FACT,
                    source_url=source if is_url else "",
                    source_title="" if is_url else source,
                    notes=(gate.relevance_reason or "")[:1200],
                )
            )
            new_state.mark_updated()
            holder.project_state = new_state
            return f"Evidence saved: {claim}"

    tools: list[BaseTool] = [
        set_north_star,
        explore_ideas,
        converge_ideas,
        commit_proposed_direction,
        record_user_decision,
        create_or_revise_plan,
        park_branch,
        save_evidence,
    ]
    tools += build_context_tools(holder, context_retriever)
    if store is not None:
        tools += _build_document_tools(holder, store, context_retriever)
    if store is not None and settings is not None:
        tools += build_research_tools(holder.project_state.project_id, store, settings)
    return tools


def _build_document_tools(
    holder: MutableStateHolder,
    store: SqliteStore,
    context_retriever: ContextRetriever,
) -> list[BaseTool]:
    project_id = holder.project_state.project_id

    @tool
    def ingest_pdf(path: str) -> str:
        """Index a local PDF file for later grounded Q&A. Ingestion only -- if the user
        asked only to ingest, acknowledge and stop."""
        pdf_path = Path(path).expanduser()
        if not pdf_path.exists():
            return f"File does not exist: {pdf_path}"
        if pdf_path.suffix.lower() != ".pdf":
            return "Only PDF files can be ingested here."
        reader = PdfReader(str(pdf_path))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        if not text.strip():
            return f"{pdf_path.name} produced no extractable text."
        document = Document(
            project_id=project_id, title=pdf_path.name, source_url=str(pdf_path), content=text
        )
        index_document(store, project_id, document)
        chunks = chunk_text(text)
        for chunk_index, chunk in enumerate(chunks):
            index_chunk(
                store,
                project_id,
                DocumentChunk(
                    document_id=document.id,
                    project_id=project_id,
                    chunk_index=chunk_index,
                    text=chunk,
                ),
            )
        return f"Ingested {pdf_path.name}: {len(reader.pages)} pages, {len(chunks)} chunks."

    @tool
    def list_indexed_documents() -> str:
        """List documents indexed for this project. Read-only."""
        docs = list_documents(store, project_id)
        if not docs:
            return "No documents indexed."
        return "\n".join(f"- {d.title or d.source_url}" for d in docs)

    @tool
    def search_documents(query: str, top_k: int = 5) -> str:
        """Search indexed documents for grounded Q&A. Returns the most relevant passages;
        quote them when you use them in your answer."""
        return context_retriever.select_document_chunks(
            project_id, query, top_k=max(1, min(top_k, 8))
        )

    return [ingest_pdf, list_indexed_documents, search_documents]


def _run_web_search(query: str, settings: Settings) -> list[ResearchSource]:
    if settings.research_retriever == "tavily":
        client = TavilyClient(api_key=settings.require_tavily_key())
        response = client.search(query, max_results=5)
        return [
            ResearchSource(
                title=result.get("title", ""),
                content=result.get("content", ""),
                url=result.get("url", ""),
            )
            for result in response.get("results", [])
        ]

    results = DDGS().text(query, max_results=5)
    return [
        ResearchSource(
            title=result.get("title", ""),
            content=result.get("body", ""),
            url=result.get("href", ""),
        )
        for result in results
    ]


def _fetch_page(url: str) -> ResearchSource:
    try:
        response = httpx.get(url, follow_redirects=True, timeout=_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return ResearchSource(title="", content=f"Could not fetch {url}: {exc}", url=url)

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    return ResearchSource(title=title, content=text, url=url)


def _summarize_sources_for_model(sources: list[ResearchSource]) -> str:
    if not sources:
        return "No results found."
    lines = []
    for source in sources:
        snippet = source.content[:500]
        lines.append(f"- {source.title or source.url} ({source.url}): {snippet}")
    return "\n".join(lines)


def _store_and_index_sources(
    project_id: str,
    store: SqliteStore,
    research_task_id: str,
    sources: list[ResearchSource],
) -> None:
    for source in sources:
        if not source.content.strip():
            continue
        document = Document(
            project_id=project_id,
            research_task_id=research_task_id,
            source_url=source.url,
            title=source.title,
            content=source.content,
        )
        index_document(store, project_id, document)
        for chunk_index, text in enumerate(chunk_text(source.content)):
            chunk = DocumentChunk(
                document_id=document.id,
                project_id=project_id,
                chunk_index=chunk_index,
                text=text,
            )
            index_chunk(store, project_id, chunk)


__all__ = [
    "ThinkingToolDeps",
    "build_context_tools",
    "build_research_tools",
    "build_thinking_tools",
]
