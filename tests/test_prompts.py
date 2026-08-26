from pathlib import Path

import pytest

from mythinking.prompts import PromptRegistry

PROMPT_DIR = Path(__file__).parents[1] / "prompts"


def test_prompt_registry_loads_research_metadata() -> None:
    registry = PromptRegistry(PROMPT_DIR)
    prompts = registry.load_all()

    assert "lead_partner:v1" in prompts
    assert "frame_analyst:v1" in prompts
    assert "drift_judge:v1" in prompts
    assert "evidence_analyst:v1" in prompts
    assert all(prompt.evidence for prompt in prompts.values())
    assert all(prompt.eval_datasets for prompt in prompts.values())


def test_latest_prompt_version_is_selected() -> None:
    prompt = PromptRegistry(PROMPT_DIR).get("lead_partner")

    assert prompt.version == 4


def test_prompt_render_requires_all_variables() -> None:
    prompt = PromptRegistry(PROMPT_DIR).get("lead_partner")

    with pytest.raises(ValueError, match="user_message"):
        prompt.render(
            {
                "project_state": "{}",
                "frame_analysis": "null",
                "drift_assessment": "null",
                "branch_command": "null",
                "evidence_ledger": "No evidence captured yet.",
            }
        )
