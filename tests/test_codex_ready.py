from pathlib import Path


def test_codex_ready_docs_exist() -> None:
    root = Path(__file__).parents[1]
    required = [
        root / "docs" / "CODEX_READY.md",
        root / "docs" / "IMPLEMENTATION_PLAN.md",
        root / "docs" / "SUBAGENT_DEVELOPMENT.md",
        root / "docs" / "SESSION_HANDOFF_TEMPLATE.md",
    ]

    assert all(path.exists() for path in required)


def test_implementation_plan_mentions_subagent_driven_milestones() -> None:
    root = Path(__file__).parents[1]
    content = (root / "docs" / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")

    assert "M1" in content
    assert "Suggested subagent split" in content
    assert "LangGraph" in content


def test_agents_file_points_to_codex_execution_contract() -> None:
    root = Path(__file__).parents[1]
    content = (root / "AGENTS.md").read_text(encoding="utf-8")

    assert "Codex execution rules" in content
    assert "docs/IMPLEMENTATION_PLAN.md" in content
