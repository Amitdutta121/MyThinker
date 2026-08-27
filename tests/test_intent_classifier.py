from pathlib import Path

from mythinking.agents.intent_classifier import IntentClassifier
from mythinking.prompts import PromptRegistry
from mythinking.state import TurnIntent

PROMPT_DIR = Path(__file__).parents[1] / "prompts"


class FakeStructuredModel:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.rendered_prompt = ""

    def invoke(self, rendered_prompt: str) -> dict:
        self.rendered_prompt = rendered_prompt
        return self.payload


class FakeModel:
    def __init__(self, payload: dict) -> None:
        self.structured_model = FakeStructuredModel(payload)

    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        return self.structured_model


def test_intent_classifier_no_longer_takes_project_state() -> None:
    model = FakeModel({"intent": TurnIntent.RESEARCH.value})
    agent = IntentClassifier(PromptRegistry(PROMPT_DIR), model)

    classification = agent.classify("can you look into whether that's true?")

    assert classification.intent is TurnIntent.RESEARCH
    rendered = model.structured_model.rendered_prompt
    assert "can you look into whether that's true?" in rendered
    assert '"schema_version"' not in rendered
