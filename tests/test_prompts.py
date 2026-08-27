from pathlib import Path

import pytest

from mythinking.prompts import PromptRegistry

PROMPT_DIR = Path(__file__).parents[1] / "prompts"


def test_prompt_registry_loads_research_metadata() -> None:
    registry = PromptRegistry(PROMPT_DIR)
    prompts = registry.load_all()

    assert "lead_partner:v1" in prompts
    assert "lead_partner:v10" in prompts
    assert "frame_analyst:v1" in prompts
    assert "evidence_analyst:v1" in prompts
    assert "profile_extractor:v1" in prompts
    assert all(prompt.evidence for prompt in prompts.values())
    assert all(prompt.eval_datasets for prompt in prompts.values())


def test_retired_prompts_are_gone() -> None:
    prompts = PromptRegistry(PROMPT_DIR).load_all()
    assert not any(key.startswith("intent_classifier:") for key in prompts)
    assert not any(key.startswith("drift_judge:") for key in prompts)


def test_latest_lead_partner_is_the_single_agent_prompt() -> None:
    prompt = PromptRegistry(PROMPT_DIR).get("lead_partner")

    assert prompt.version == 10
    # The single-agent system prompt is static; the compact status block is
    # injected by middleware, so it renders with no context variables.
    assert "Thinker" in prompt.render({})


def test_latest_researcher_prompt_version_is_selected() -> None:
    prompt = PromptRegistry(PROMPT_DIR).get("researcher")

    assert prompt.version == 4


def test_specialist_prompt_render_still_requires_all_variables() -> None:
    prompt = PromptRegistry(PROMPT_DIR).get("frame_analyst")

    with pytest.raises(ValueError, match="user_message"):
        prompt.render(
            {
                "north_star_brief": "Title: x",
                "assumptions": "none",
                "open_questions": "none",
            }
        )
