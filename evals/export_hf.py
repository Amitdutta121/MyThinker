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
LOGO_URL = "https://raw.githubusercontent.com/Amitdutta121/MyThinker/main/docs/assets/logo.svg"
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

<img src="{LOGO_URL}" alt="MyThinking logo" width="72">

# Dataset Card for MyThinking Behavioral Evals

Behavioral test cases for a stateful, tool-using LLM agent. Each case checks
**what the agent does**: which tools it calls, in what order, and how its
persistent project state changes. It also checks **how it responds**, through
natural-language expectations scored by an LLM judge.

| Cases | Judged expectations | With deterministic checks | Multi-turn | With seed documents |
| :---: | :---: | :---: | :---: | :---: |
| {len(rows)} | {n_expect} | {n_checked} | {n_multi} | {n_docs} |

## Dataset Details

### Dataset Description

The cases were written for [MyThinking]({GITHUB_URL}), a single-agent "thinking
partner" that keeps a persistent project board (North Star, branches, decisions,
evidence, next-action plan). Every board-mutating tool has a hard precondition.
The cases probe whether the agent calls the right tool at the right time, refuses
to mutate state when it shouldn't, keeps sources separate from evidence, and
resists prompt injection from documents.

- **Curated by:** Amit Dutta
- **Language:** English
- **License:** MIT

### Dataset Sources

- **Repository:** {GITHUB_URL}
- **Runner and full check schema:** [`evals/runner.py`]({GITHUB_URL}/blob/main/evals/runner.py)

## Uses

### Direct Use

- Regression-test MyThinking across models or prompt versions with
  `uv run python evals/runner.py --judge`.
- Use the judged `expectations` as a rubric for other stateful, tool-using
  agents: framing, convergence, research scoping, and refusing state changes.

### Out-of-Scope Use

- **Not a training set.** With {len(rows)} hand-written cases, it is meant for
  evaluation only.
- The deterministic `check` fields assume MyThinking's tool names and board
  schema, and don't transfer to other agents without remapping.
- **Not a leaderboard.** This release has no reference model results.

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

Prompt-only agents fail quietly. They commit a direction the user never
approved, promote a web page to "evidence", or rewrite the plan on an off-topic
question. These cases pin down those failure modes as concrete, checkable
behavior so that a prompt or model change can't regress them unnoticed.

### Source Data

The project author wrote every case by hand while developing MyThinking. Each one
targets a specific product rule or a failure seen during development. Seed
documents are short synthetic texts. None of the data comes from real users.

### Personal and Sensitive Information

None. User messages and documents are synthetic. The `profile_extraction` and
`memory_policy` cases use made-up personal details to test that the agent does
*not* store sensitive information.

## Bias, Risks, and Limitations

- **Small and single-author.** Coverage reflects one designer's view of a good
  thinking partner. Some categories have only one or two cases.
- **Judge dependence.** `expectations` are scored by an LLM judge, which can
  disagree with human raters. Prefer the deterministic checks when they exist.
- **System-specific.** Tool names and state fields are MyThinking's.

## More Information

The case file is the source of truth: `evals/cases.jsonl` in the repository.
This dataset is generated from it by `evals/export_hf.py`.

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
