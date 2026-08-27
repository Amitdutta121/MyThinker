"""Intent Classifier specialist for semantic turn routing."""

from typing import Any

from pydantic import BaseModel

from mythinking.prompts import PromptRegistry
from mythinking.state import IntentClassification


class IntentClassifier:
    """Call the intent-classification prompt and enforce a typed response contract."""

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        *,
        prompt_id: str = "intent_classifier",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def classify(self, user_message: str) -> IntentClassification:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render({"user_message": user_message})
        structured_model = self.model.with_structured_output(IntentClassification)
        response = structured_model.invoke(rendered)
        return _validate_model_output(response, IntentClassification)


def _validate_model_output(payload: Any, schema: type[BaseModel]) -> BaseModel:
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)
