"""Behavioral eval runner for the single-agent Thinker.

Feeds each case in `cases.jsonl` through `ThinkingRuntime` on a fresh, throwaway
project, captures the tool trace and the board delta for every turn, runs any
deterministic `check` / `check_turns` blocks, and (with `--judge`) asks the
model to score each natural-language expectation.

This DOES make live model calls -- run it deliberately, not in CI:

    uv run python evals/runner.py            # trace + deterministic checks
    uv run python evals/runner.py --judge    # + LLM-judged expectations (judge = agent model)
    uv run python evals/runner.py --judge --judge-model deepseek/deepseek-chat
    uv run python evals/runner.py --only commit-exact-proposal,journey-end-to-end

Exit code is non-zero if any deterministic check failed.

Case schema (one JSON object per line in cases.jsonl):

    id            required  unique slug
    category      required  grouping label
    input         a single user message                 (use this OR `turns`)
    turns         list of turn items, one shared thread. Each item is either a
                  string (a user message) or {"reset": true} (start a brand-new
                  project/thread for the turns that follow -- for cross-project
                  isolation checks).
    setup         partial ProjectState dict, seeded and persisted before turn 1.
                  May also carry `documents`: a list of
                  {"title": "...", "pages": ["p1 text", "p2 text", ...]} that are
                  chunked and indexed into the document store so `search_documents`
                  can retrieve them with `[[title p.N]]` citation tags.
    check         deterministic assertions applied to the FINAL turn (see
                  `_eval_check`); scalar deltas are whole-case (start -> end).
    check_turns   list of per-turn `check` dicts; `check_turns[i]` is applied
                  after the i-th message turn (reset items are not counted).
                  Scalar deltas here are for that turn alone.
    expectations  natural-language checks, scored only with --judge

`check` / `check_turns` keys, all optional. Scalar values may be a literal
(equality) or an object combining `{"gte": n}`, `{"lte": n}`, `{"eq": n}`,
`{"is_null": true|false}`:

    tools_include        list[str]  every name must appear in the turn's trace
    tools_exclude        list[str]  none may appear
    tool_order           list[str]  these names first appear in this relative order
    north_star_set       bool       a North Star was established (delta)
    branches_added       int        net branches added (delta)
    parked_ideas_added   int        (delta)
    decisions_added      int        (delta)
    evidence_added       int        (delta)
    plan_steps           int        non-completed next actions afterwards (absolute)
    plan_steps_live      int        non-completed AND non-stale afterwards (absolute)
    plan_steps_stale     int        non-completed AND stale afterwards (absolute)
    committed_direction  str|null   north_star.current_hypothesis (null = empty)
    proposal_cleared     bool       proposal is None afterwards
    proposal_statement   str|null   proposal.statement afterwards
    mode                 str        current_mode value afterwards
    answer_contains      str        case-insensitive substring of the answer
    answer_not_contains  str        case-insensitive substring absent from the answer
"""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from mythinking.config import Settings, get_settings
from mythinking.documents import Document, DocumentChunk, chunk_pages
from mythinking.llm import create_chat_model
from mythinking.retrieval import index_chunk, index_document
from mythinking.runtime import ThinkingRuntime
from mythinking.state import ProjectState, TurnStreamEventType

CASES_PATH = Path(__file__).with_name("cases.jsonl")

Verdict = tuple[str, bool, str]


@dataclass
class TurnRecord:
    tools: list[str]
    answer: str
    delta: dict[str, object]  # relative to the state right before this turn
    after: ProjectState
    fresh: bool = False  # this turn opened a brand-new project (followed a {"reset": true})


@dataclass
class CaseResult:
    case_id: str
    category: str
    tools: list[str]  # the final turn's trace
    answer: str  # the final turn's answer
    delta: dict[str, object]  # whole-case delta (start -> end)
    turns: list[TurnRecord] = field(default_factory=list)
    profile: dict[str, object] = field(default_factory=dict)  # user profile after the run
    verdicts: list[Verdict] = field(default_factory=list)


def load_cases(only: set[str] | None) -> list[dict]:
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line]
    return [c for c in cases if only is None or c["id"] in only]


def _board_delta(before: ProjectState, after: ProjectState) -> dict[str, object]:
    live = sum(1 for a in after.next_actions if not a.completed and not a.stale)
    stale = sum(1 for a in after.next_actions if not a.completed and a.stale)
    return {
        "north_star_set": bool(after.north_star.problem_statement)
        and not before.north_star.problem_statement,
        "branches_added": len(after.branches) - len(before.branches),
        "parked_ideas_added": len(after.parked_ideas) - len(before.parked_ideas),
        "decisions_added": len(after.decisions) - len(before.decisions),
        "evidence_added": len(after.evidence) - len(before.evidence),
        "proposal": after.proposal.statement if after.proposal else None,
        "committed_direction": after.north_star.current_hypothesis or None,
        "plan_steps": sum(1 for a in after.next_actions if not a.completed),
        "plan_steps_live": live,
        "plan_steps_stale": stale,
    }


def _index_seed_document(runtime: ThinkingRuntime, project_id: str, doc: dict) -> None:
    store = getattr(runtime, "store", None)
    if store is None:
        raise RuntimeError("case seeds `documents` but the runtime has no document store")
    pages = doc.get("pages") or ([doc["content"]] if doc.get("content") else [])
    title = doc.get("title", "seed.pdf")
    document = Document(
        project_id=project_id,
        title=title,
        source_url=doc.get("source_url", ""),
        content="\n\n".join(pages),
    )
    index_document(store, project_id, document)
    for chunk_index, (page_number, chunk) in enumerate(chunk_pages(pages)):
        index_chunk(
            store,
            project_id,
            DocumentChunk(
                document_id=document.id,
                project_id=project_id,
                chunk_index=chunk_index,
                page=page_number,
                document_title=title,
                text=chunk,
            ),
        )


def _seed_state(runtime: ThinkingRuntime, setup: dict) -> str | None:
    """Persist a partial ProjectState (+ any seed documents). Returns its id, or None."""
    documents = setup.get("documents") or []
    fields = {k: v for k, v in setup.items() if k != "documents"}
    if not fields and not documents:
        return None
    state = ProjectState.model_validate(fields) if fields else ProjectState()
    runtime.repository.save(state)
    for doc in documents:
        _index_seed_document(runtime, state.project_id, doc)
    return state.project_id


def _turn_items(case: dict) -> list:
    return case.get("turns") or [case["input"]]


def run_case(runtime: ThinkingRuntime, case: dict) -> CaseResult:
    project_id = _seed_state(runtime, case.get("setup", {}))
    case_before = (runtime.get_project_state(project_id) if project_id else None) or ProjectState()

    records: list[TurnRecord] = []
    fresh_next = False
    for item in _turn_items(case):
        if isinstance(item, dict) and item.get("reset"):
            project_id = None
            fresh_next = True
            continue
        message = item if isinstance(item, str) else item["message"]
        turn_before = (
            runtime.get_project_state(project_id) if project_id else None
        ) or ProjectState()

        tools: list[str] = []
        turn = None
        for event in runtime.stream_turn(message, project_id=project_id):
            if event.type is TurnStreamEventType.NODE and event.node:
                tools.append(event.node)
            elif event.type is TurnStreamEventType.TURN:
                turn = event.turn
                project_id = turn.project_id
        assert turn is not None

        after = runtime.get_project_state(project_id) or ProjectState()
        records.append(
            TurnRecord(
                tools=tools,
                answer=turn.message,
                delta=_board_delta(turn_before, after),
                after=after,
                fresh=fresh_next,
            )
        )
        fresh_next = False

    assert records, "case produced no message turns"
    final = records[-1]
    try:
        prof = runtime.get_user_profile()
        profile = {
            "role": prof.role,
            "expertise": list(prof.expertise),
            "working_style": list(prof.working_style),
        }
    except Exception:
        profile = {}
    return CaseResult(
        case_id=case["id"],
        category=case["category"],
        tools=final.tools,
        answer=final.answer,
        profile=profile,
        delta=_board_delta(case_before, final.after),
        turns=records,
    )


def _cmp(expected: object, got: object) -> bool:
    """Literal equality, or a `{gte|lte|eq|is_null: ...}` comparison object."""
    if not isinstance(expected, dict):
        return got == expected
    checks = (
        "eq" not in expected or got == expected["eq"],
        "gte" not in expected or (got is not None and got >= expected["gte"]),
        "lte" not in expected or (got is not None and got <= expected["lte"]),
        "is_null" not in expected or (got is None) == expected["is_null"],
    )
    return all(checks)


def _eval_check(
    spec: dict,
    tools: list[str],
    delta: dict[str, object],
    after: ProjectState,
    answer: str,
) -> list[Verdict]:
    verdicts: list[Verdict] = []

    def record(name: str, ok: bool, got: object) -> None:
        verdicts.append((name, bool(ok), f"got {got!r}"))

    if "tools_include" in spec:
        missing = [t for t in spec["tools_include"] if t not in tools]
        record(f"tools_include {spec['tools_include']}", not missing, tools)
    if "tools_exclude" in spec:
        hit = [t for t in spec["tools_exclude"] if t in tools]
        record(f"tools_exclude {spec['tools_exclude']}", not hit, tools)
    if "tool_order" in spec:
        idx = [tools.index(t) for t in spec["tool_order"] if t in tools]
        ordered = len(idx) == len(spec["tool_order"]) and idx == sorted(idx)
        record(f"tool_order {spec['tool_order']}", ordered, tools)

    scalars = {
        "north_star_set": lambda: delta["north_star_set"],
        "branches_added": lambda: delta["branches_added"],
        "parked_ideas_added": lambda: delta["parked_ideas_added"],
        "decisions_added": lambda: delta["decisions_added"],
        "evidence_added": lambda: delta["evidence_added"],
        "plan_steps": lambda: delta["plan_steps"],
        "plan_steps_live": lambda: delta["plan_steps_live"],
        "plan_steps_stale": lambda: delta["plan_steps_stale"],
        "committed_direction": lambda: after.north_star.current_hypothesis or None,
        "proposal_cleared": lambda: after.proposal is None,
        "proposal_statement": lambda: after.proposal.statement if after.proposal else None,
        "mode": lambda: after.current_mode.value,
    }
    for key, getter in scalars.items():
        if key in spec:
            got = getter()
            record(f"{key} {spec[key]!r}", _cmp(spec[key], got), got)

    if "answer_contains" in spec:
        needle = str(spec["answer_contains"]).lower()
        record(
            f"answer_contains {spec['answer_contains']!r}", needle in answer.lower(), answer[:100]
        )
    if "answer_not_contains" in spec:
        needle = str(spec["answer_not_contains"]).lower()
        record(
            f"answer_not_contains {spec['answer_not_contains']!r}",
            needle not in answer.lower(),
            answer[:100],
        )
    return verdicts


def check_case(case: dict, result: CaseResult) -> list[Verdict]:
    """Deterministic, model-free scoring of a case's `check` / `check_turns` blocks."""
    verdicts: list[Verdict] = []

    final_spec = case.get("check")
    if final_spec:
        verdicts += [
            (f"[final] {name}", ok, why)
            for name, ok, why in _eval_check(
                final_spec, result.tools, result.delta, result.turns[-1].after, result.answer
            )
        ]

    for i, spec in enumerate(case.get("check_turns") or []):
        if not spec:
            continue
        if i >= len(result.turns):
            verdicts.append((f"[turn {i + 1}] present", False, "case ended before this turn"))
            continue
        rec = result.turns[i]
        verdicts += [
            (f"[turn {i + 1}] {name}", ok, why)
            for name, ok, why in _eval_check(spec, rec.tools, rec.delta, rec.after, rec.answer)
        ]
    return verdicts


_JUDGE_SYSTEM = """You grade ONE behavioral expectation for an AI "thinking partner" assistant \
that talks to a user while maintaining a structured idea board (North Star, idea branches,
an optional single proposal, decisions, evidence, and a plan).

Grading rules:
- Judge ONLY the stated expectation. Ignore every other quality of the response
  (style, verbosity, unrelated mistakes).
- Use ONLY the evidence given: the per-turn user messages, the tools each turn
  called, the whole-case board delta, the final board state, and the assistant's
  replies. Do not assume anything not shown.
- The "tools called" list for each turn is COMPLETE and AUTHORITATIVE. If a tool
  name is listed, it was invoked; if it is not listed, it was not. A tool being
  invoked does not mean it succeeded -- cross-check the board delta / final state
  (a refused action leaves the board unchanged).
- Read-only lookup tools (get_project_snapshot, get_evidence_ledger,
  get_branch_alternatives, get_next_actions_plan, get_open_research_tasks,
  list_indexed_documents, search_documents) never change state. A reply that
  quotes, summarizes, or cites a document (e.g. "[[file.pdf p.2]]") is NOT
  "saving/promoting evidence" -- only a save_evidence call with evidence_added > 0
  counts as that.
- NEGATIVE / absence expectations -- phrased as "does not X", "never X",
  "ignores X", "reads none of ... as ...", "without X", "leaves ... unchanged",
  "does not silently ...": these are SATISFIED when the transcript and board
  delta show X did not happen. Absence is sufficient proof. Do NOT require the
  assistant to explicitly announce that it refrained, and do NOT fail it for
  "no evidence that it ignored X" -- the board being unchanged IS that evidence.
- You cannot see the assistant's private reasoning. For expectations about
  "using judgment", "recognizing" something, or "entering a mode", judge by
  observable behavior: a reply that visibly engages with the thing (addresses
  it, asks a pointed question about it, acts on it) satisfies it; only fail if
  the reply ignores it entirely.
- A North Star shown as "(none)" / "(not established)" / "Untitled idea" all mean
  NO North Star is set; that is the correct state for a brand-new project.
- A turn marked [NEW PROJECT] starts a fresh, empty project; nothing from earlier
  turns carries over and nothing should be expected to. "No North Star yet" and not
  knowing anything stated earlier is the CORRECT behavior there.
- The verdict is binary. If the evidence does not clearly satisfy the expectation,
  return false. "Partially" is false.
- For a multi-turn case, judge across ALL turns shown, not just the last.

Reply with ONE minified JSON object and nothing else:
{"pass": true|false, "why": "<=25 words, concrete, tied to the evidence"}"""


def _final_state_summary(state: ProjectState) -> str:
    ns = state.north_star
    active = [b.name for b in state.branches if b.status.value == "active"]
    parked = [b.name for b in state.branches if b.status.value == "parked"]
    return "\n".join(
        [
            f"north star: {ns.problem_statement or '(none)'}",
            f"committed direction: {ns.current_hypothesis or '(none)'}",
            f"open proposal: {state.proposal.statement if state.proposal else '(none)'}",
            f"active branches: {active or '(none)'}",
            f"parked branches: {parked or '(none)'}  parked_ideas: {len(state.parked_ideas)}",
            f"decisions: {len(state.decisions)}  evidence: {len(state.evidence)}  "
            f"plan steps: {len(state.next_actions)} "
            f"({sum(1 for a in state.next_actions if a.stale)} stale)",
        ]
    )


def _judge_evidence(case: dict, result: CaseResult) -> str:
    messages = [
        t if isinstance(t, str) else t.get("message", "")
        for t in _turn_items(case)
        if not (isinstance(t, dict) and t.get("reset"))
    ]
    blocks: list[str] = []
    for i, rec in enumerate(result.turns, start=1):
        user = messages[i - 1] if i - 1 < len(messages) else "(message)"
        marker = (
            " [NEW PROJECT: a brand-new empty project on a fresh thread; every earlier "
            "turn belongs to a different, now-inaccessible project]"
            if rec.fresh
            else ""
        )
        blocks.append(
            f"--- Turn {i}{marker} ---\n"
            f"user: {user}\n"
            f"tools called: {rec.tools or 'none'}\n"
            f"assistant: {rec.answer.strip()}"
        )
    return (
        "TRANSCRIPT\n"
        + "\n\n".join(blocks)
        + "\n\nWHOLE-CASE BOARD DELTA\n"
        + json.dumps(result.delta)
        + "\n\nFINAL BOARD STATE\n"
        + _final_state_summary(result.turns[-1].after)
        + "\n\nUSER PROFILE AFTER RUN\n"
        + json.dumps(result.profile or {})
    )


def _parse_judge_reply(raw: str) -> tuple[bool, str] | None:
    text = raw.strip()
    if "</think>" in text:  # reasoning models that inline their scratchpad
        text = text.split("</think>", 1)[1].strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    try:
        obj = json.loads(text[text.index("{") : text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None
    if "pass" not in obj:
        return None
    return bool(obj["pass"]), str(obj.get("why", "")).strip()


def _ask_judge(model, user_content: str) -> tuple[bool, str]:
    conversation = [SystemMessage(_JUDGE_SYSTEM), HumanMessage(user_content)]
    raw = ""
    for _ in range(2):
        reply = model.invoke(conversation).content
        raw = reply if isinstance(reply, str) else str(reply)
        parsed = _parse_judge_reply(raw)
        if parsed is not None:
            return parsed
        conversation.append(
            HumanMessage(
                'That was not valid JSON. Reply with ONLY {"pass": true|false, "why": "..."}'
            )
        )
    return False, f"unparseable judge reply: {raw[:160]}"


def judge(model, case: dict, result: CaseResult) -> list[Verdict]:
    """Score each natural-language expectation with an LLM judge (one call per expectation)."""
    evidence = _judge_evidence(case, result)
    verdicts: list[Verdict] = []
    for expectation in case.get("expectations", []):
        ok, why = _ask_judge(model, f"{evidence}\n\n=== EXPECTATION TO GRADE ===\n{expectation}")
        verdicts.append((f"[judge] {expectation}", ok, why))
    return verdicts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", action="store_true", help="LLM-score each expectation")
    parser.add_argument(
        "--judge-model",
        default="",
        help="model slug for the judge (default: same as the agent). e.g. deepseek/deepseek-chat",
    )
    parser.add_argument("--only", default="", help="comma-separated case ids")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_api_key:
        print("Set OPENROUTER_API_KEY to run evals (they make live model calls).")
        return 1

    only = {x for x in args.only.split(",") if x} or None
    cases = load_cases(only)
    judge_model = None
    if args.judge:
        judge_model = create_chat_model(settings, model=args.judge_model or None, temperature=0)
        judge_name = args.judge_model or settings.openrouter_model
        print(f"judge model: {judge_name}")

    det_pass = det_total = 0
    judge_pass = judge_total = 0
    deterministic_failures = 0
    errored = 0
    ran = 0
    for case in cases:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_settings = Settings(
                    _env_file=None,
                    openrouter_api_key=settings.openrouter_api_key,
                    openrouter_model=settings.openrouter_model,
                    data_dir=Path(tmp),
                    prompt_dir=Path("prompts"),
                    enable_profile_extraction=True,
                )
                runtime = ThinkingRuntime(settings=run_settings)
                try:
                    result = run_case(runtime, case)
                    deterministic = check_case(case, result)
                    judged = judge(judge_model, case, result) if judge_model is not None else []
                    result.verdicts = deterministic + judged
                finally:
                    store_cm = getattr(runtime, "_store_cm", None)
                    if store_cm is not None:
                        store_cm.__exit__(None, None, None)
        except Exception as exc:  # one bad case must not abort the whole suite
            message = f"{type(exc).__name__}: {exc}"
            print(f"\n=== {case['id']} [{case.get('category', '?')}] ===")
            print(f"  [ERROR] {' '.join(message.split())[:300]}")
            errored += 1
            if "PaymentRequired" in message or "available credits" in message:
                print(
                    "\nSTOPPING: OpenRouter credits exhausted. Re-run when credits are available."
                )
                break
            continue

        ran += 1
        deterministic_failures += sum(1 for _, ok, _ in deterministic if not ok)
        det_pass += sum(1 for _, ok, _ in deterministic if ok)
        det_total += len(deterministic)
        judge_pass += sum(1 for _, ok, _ in judged if ok)
        judge_total += len(judged)

        print(f"\n=== {result.case_id} [{result.category}] ===")
        print(f"tools (final turn): {' -> '.join(result.tools) or '(none)'}")
        print(f"delta (whole case): {json.dumps(result.delta)}")
        print(f"answer (final turn): {result.answer[:200].replace(chr(10), ' ')}")
        for name, ok, why in result.verdicts:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name} -- {' '.join(why.split())[:200]}")

    print(f"\ncases run: {ran}/{len(cases)}" + (f"  ({errored} errored)" if errored else ""))
    if det_total:
        print(f"deterministic: {det_pass}/{det_total} passed")
    if judge_total:
        print(f"judge:         {judge_pass}/{judge_total} expectations passed")
    if deterministic_failures:
        print(f"{deterministic_failures} deterministic check(s) failed")
    return 1 if deterministic_failures or errored else 0


if __name__ == "__main__":
    raise SystemExit(main())
