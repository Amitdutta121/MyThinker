"""Behavioral eval runner for the single-agent Thinker.

Feeds each case in `cases.jsonl` through `ThinkingRuntime.run_turn` on a fresh,
throwaway project, captures the tool trace and the board delta, and (with
`--judge`) asks the model to score each natural-language expectation.

This DOES make live model calls -- run it deliberately, not in CI:

    uv run python evals/runner.py            # trace only, no scoring
    uv run python evals/runner.py --judge    # + LLM-judged pass/fail
    uv run python evals/runner.py --only commit-exact-proposal,plan-blocked-without-commitment
"""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from mythinking.config import Settings, get_settings
from mythinking.llm import create_chat_model
from mythinking.runtime import ThinkingRuntime
from mythinking.state import ProjectState, TurnStreamEventType

CASES_PATH = Path(__file__).with_name("cases.jsonl")


@dataclass
class CaseResult:
    case_id: str
    category: str
    tools: list[str]
    answer: str
    delta: dict[str, object]
    verdicts: list[tuple[str, bool, str]] = field(default_factory=list)


def load_cases(only: set[str] | None) -> list[dict]:
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line]
    return [c for c in cases if only is None or c["id"] in only]


def _board_delta(before: ProjectState, after: ProjectState) -> dict[str, object]:
    return {
        "north_star_set": bool(after.north_star.problem_statement)
        and not before.north_star.problem_statement,
        "branches_added": len(after.branches) - len(before.branches),
        "proposal": after.proposal.statement if after.proposal else None,
        "committed_direction": after.north_star.current_hypothesis or None,
        "decisions_added": len(after.decisions) - len(before.decisions),
        "evidence_added": len(after.evidence) - len(before.evidence),
        "plan_steps": sum(1 for a in after.next_actions if not a.completed),
    }


def run_case(runtime: ThinkingRuntime, case: dict) -> CaseResult:
    tools: list[str] = []
    turn = None
    for event in runtime.stream_turn(case["input"]):
        if event.type is TurnStreamEventType.NODE and event.node:
            tools.append(event.node)
        elif event.type is TurnStreamEventType.TURN:
            turn = event.turn
    assert turn is not None
    after = runtime.get_project_state(turn.project_id) or ProjectState()
    return CaseResult(
        case_id=case["id"],
        category=case["category"],
        tools=tools,
        answer=turn.message,
        delta=_board_delta(ProjectState(), after),
    )


def judge(model, case: dict, result: CaseResult) -> list[tuple[str, bool, str]]:
    verdicts: list[tuple[str, bool, str]] = []
    for expectation in case["expectations"]:
        prompt = (
            "You are grading one behavioral expectation for an AI thinking assistant.\n\n"
            f"USER MESSAGE:\n{case['input']}\n\n"
            f"TOOLS THE ASSISTANT CALLED: {result.tools or 'none'}\n"
            f"BOARD DELTA: {json.dumps(result.delta)}\n"
            f"ASSISTANT ANSWER:\n{result.answer}\n\n"
            f"EXPECTATION: {expectation}\n\n"
            'Reply as JSON: {"pass": true|false, "why": "<one sentence>"}'
        )
        raw = model.invoke(prompt).content
        try:
            parsed = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
            verdicts.append((expectation, bool(parsed.get("pass")), str(parsed.get("why", ""))))
        except (ValueError, KeyError):
            verdicts.append((expectation, False, f"unparseable judge reply: {raw[:120]}"))
    return verdicts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", action="store_true", help="LLM-score each expectation")
    parser.add_argument("--only", default="", help="comma-separated case ids")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_api_key:
        print("Set OPENROUTER_API_KEY to run evals (they make live model calls).")
        return 1

    only = {x for x in args.only.split(",") if x} or None
    cases = load_cases(only)
    judge_model = create_chat_model(settings, temperature=0) if args.judge else None

    total_pass = 0
    total_checks = 0
    for case in cases:
        with tempfile.TemporaryDirectory() as tmp:
            run_settings = Settings(
                _env_file=None,
                openrouter_api_key=settings.openrouter_api_key,
                openrouter_model=settings.openrouter_model,
                data_dir=Path(tmp),
                prompt_dir=Path("prompts"),
            )
            runtime = ThinkingRuntime(settings=run_settings)
            result = run_case(runtime, case)
            if judge_model is not None:
                result.verdicts = judge(judge_model, case, result)

        print(f"\n=== {result.case_id} [{result.category}] ===")
        print(f"tools: {' -> '.join(result.tools) or '(none)'}")
        print(f"delta: {json.dumps(result.delta)}")
        print(f"answer: {result.answer[:200].replace(chr(10), ' ')}")
        for expectation, ok, why in result.verdicts:
            total_checks += 1
            total_pass += int(ok)
            print(f"  [{'PASS' if ok else 'FAIL'}] {expectation} -- {why}")

    if total_checks:
        print(f"\n{total_pass}/{total_checks} expectations passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
