import json
from pathlib import Path


def test_eval_cases_are_valid_and_unique() -> None:
    path = Path(__file__).parents[1] / "evals" / "cases.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    case_ids = [case["id"] for case in cases]

    assert len(cases) >= 5
    assert len(case_ids) == len(set(case_ids))
    assert all(case["expectations"] for case in cases)
