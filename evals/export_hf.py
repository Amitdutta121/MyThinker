"""Export `cases.jsonl` as a Hugging Face Hub dataset folder.

The raw cases have heterogeneous nested fields (`setup`, `check`, `check_turns`
carry different keys per case; `turns` mixes strings and `{"reset": true}`), which
the Hub's Arrow-based viewer cannot infer a single schema for. This export keeps
every row on one flat, stable schema by storing those fields as JSON strings.

    uv run python evals/export_hf.py --repo-id <user>/mythinking-evals
    hf upload <user>/mythinking-evals dist/hf-dataset --repo-type dataset

Stdlib only; makes no network or model calls.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

CASES_PATH = Path(__file__).with_name("cases.jsonl")
DEFAULT_OUT = Path(__file__).parents[1] / "dist" / "hf-dataset"
DEFAULT_REPO_ID = "amitdutta121/mythinking-evals"
GITHUB_URL = "https://github.com/Amitdutta121/MyThinker"
JSON_FIELDS = ("turns", "setup", "check", "check_turns")

CATEGORY_NOTES = {
    "state_integrity": "No board mutation on off-topic or general questions; "
    "document contents treated as data, not instructions",
    "convergence_quality": "Compares real branches; proposes before committing; "
    "commits the exact proposal",
    "unsupported_invention": "Separates unverified claims from sourced facts",
    "framing_accuracy": "Sets a North Star only when the goal is clear; no invented users",
    "branch_navigation": "Switches, returns to, and parks branches without losing them",
    "intent_classification": "Picks the right tool from paraphrased requests",
    "scoped_research": "Research stays on the question; cites document pages",
    "next_action_planning": "Plans only from a committed direction; small time-boxed steps",
    "focus_retention": "Recognizes tangents and parks them",
    "alternative_generation": "Produces distinct alternatives after anchoring",
    "question_usefulness": "Asks one consequential narrowing question",
    "anti_fixation": "Asks for the user's own thinking before offering ideas",
    "memory_policy": "Does not silently persist sensitive details",
    "ambiguous_drift_judgment": "Asks rather than guessing which part of the project is meant",
    "profile_extraction": "Records role and expertise, never sensitive details",
}


def to_row(case: dict) -> dict:
    turns = case.get("turns")
    row = {
        "id": case["id"],
        "category": case["category"],
        "input": case.get("input"),
        "num_turns": 1 if turns is None else sum(isinstance(t, str) for t in turns),
        "has_deterministic_check": "check" in case or "check_turns" in case,
        "has_documents": bool(case.get("setup", {}).get("documents")),
        "expectations": list(case["expectations"]),
    }
    for name in JSON_FIELDS:
        value = case.get(name)
        row[name] = None if value is None else json.dumps(value, ensure_ascii=False)
    return row


def render_card(rows: list[dict], repo_id: str = DEFAULT_REPO_ID) -> str:
    categories = Counter(r["category"] for r in rows)
    table = "\n".join(
        f"| `{c}` | {n} | {CATEGORY_NOTES.get(c, '')} |" for c, n in categories.most_common()
    )
    n_checked = sum(r["has_deterministic_check"] for r in rows)
    n_multi = sum(r["num_turns"] > 1 for r in rows)
    n_docs = sum(r["has_documents"] for r in rows)
    n_expect = sum(len(r["expectations"]) for r in rows)
    return f"""---
license: mit
language:
- en
pretty_name: MyThinking Behavioral Evals
size_categories:
- n<1K
task_categories:
- text-generation
tags:
- agents
- tool-use
- llm-evaluation
- llm-as-a-judge
- multi-turn
configs:
- config_name: default
  data_files:
  - split: test
    path: data/test.jsonl
---

# Dataset Card for MyThinking Behavioral Evals

Test cases for [MyThinking]({GITHUB_URL}), an LLM agent that keeps a project
board (goal, alternatives, decisions, evidence, plan) and changes it through
tools. Each case is one or more user messages plus checks on what the agent
should do: which tools it calls, how the board changes, and what the reply
should contain.

There are {len(rows)} cases with {n_expect} judged expectations in total.
{n_checked} cases also have deterministic checks, {n_multi} are multi-turn, and
{n_docs} come with seed documents for retrieval.

## Dataset Details

### Dataset Description

The agent's board-changing tools check preconditions in code; for example,
`commit_proposed_direction` refuses unless the user's message approves the
proposal. Most cases test those boundaries: does the agent call the right tool,
leave the board alone when it should, keep fetched pages out of the evidence
ledger until they're saved properly, and ignore instructions embedded in
documents.

- Curated by: Amit Dutta
- Language: English
- License: MIT

### Dataset Sources

- Repository: {GITHUB_URL}
- Runner and check schema: [`evals/runner.py`]({GITHUB_URL}/blob/main/evals/runner.py)

## Uses

### Direct Use

Regression testing MyThinking across models and prompt versions
(`uv run python evals/runner.py --judge`). The plain-language expectations can
also be borrowed as a rubric for other agents that keep state between turns.

### Out-of-Scope Use

It's too small for training. The deterministic checks use MyThinking's tool
names and state fields, so they won't apply to another agent without
remapping. No model results are published yet, so there is nothing to compare
against.

## Dataset Structure

One split, `test`, with {len(rows)} rows.

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Unique slug |
| `category` | string | Behavior under test (see below) |
| `input` | string \\| null | Single user message; null when `turns` is used |
| `turns` | JSON string \\| null | User messages; `{{"reset": true}}` = fresh project |
| `num_turns` | int | Number of user messages |
| `setup` | JSON string \\| null | Project state seeded before turn 1 (may hold `documents`) |
| `check` | JSON string \\| null | Deterministic assertions on the final turn |
| `check_turns` | JSON string \\| null | Per-turn deterministic assertions |
| `expectations` | list[string] | Natural-language checks for an LLM judge |
| `has_deterministic_check` | bool | `check` or `check_turns` present |
| `has_documents` | bool | `setup` seeds documents for retrieval |

`turns`, `setup`, `check`, and `check_turns` are JSON-encoded because their
shape varies per case. Check keys include `tools_include`, `tools_exclude`,
`tool_order`, `north_star_set`, `decisions_added`, `evidence_added`,
`proposal_cleared`, `plan_steps`, `mode`, and `answer_contains`.

### Categories

| Category | Cases | What it tests |
| --- | :---: | --- |
{table}

### Usage

```python
import json
from datasets import load_dataset

ds = load_dataset("{repo_id}", split="test")
case = ds[0]
turns = json.loads(case["turns"]) if case["turns"] else [case["input"]]
check = json.loads(case["check"]) if case["check"] else {{}}
```

## Dataset Creation

### Curation Rationale

I wrote these while building MyThinking, mostly after seeing the agent do the
wrong thing: commit a direction nobody approved, save a web page as evidence,
or rewrite the plan in response to an unrelated question. Each case pins one of
those behaviors down so a prompt or model change can't quietly bring it back.

### Source Data

All cases were written by hand by the project author. Seed documents are short
made-up texts. Nothing comes from real users.

### Personal and Sensitive Information

None. The `profile_extraction` and `memory_policy` cases include invented
personal details on purpose, to check that the agent doesn't store them.

## Bias, Risks, and Limitations

One person wrote all the cases, so coverage follows one view of what a good
thinking partner does, and several categories have only one or two cases. The
expectations are scored by an LLM judge, which won't always agree with a human;
the deterministic checks are more reliable where they exist.

## More Information

`evals/cases.jsonl` in the repository is the source of truth. This dataset is
generated from it with `evals/export_hf.py`.

## Dataset Card Contact

Open an issue at {GITHUB_URL}/issues.
"""


def export(
    out_dir: Path, cases_path: Path = CASES_PATH, repo_id: str = DEFAULT_REPO_ID
) -> list[dict]:
    lines = cases_path.read_text(encoding="utf-8").splitlines()
    rows = [to_row(json.loads(line)) for line in lines if line.strip()]
    (out_dir / "data").mkdir(parents=True, exist_ok=True)
    with (out_dir / "data" / "test.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    card = render_card(rows, repo_id)
    (out_dir / "README.md").write_text(card, encoding="utf-8", newline="\n")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID, help="e.g. user/mythinking-evals")
    args = parser.parse_args()
    rows = export(args.out, repo_id=args.repo_id)
    print(f"Wrote {len(rows)} cases to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
