"""Profile Extractor specialist for capturing stable, cross-project user facts."""

from typing import Any

from pydantic import BaseModel

from mythinking.prompts import PromptRegistry
from mythinking.state import ProfileAnalysis, UserProfile


class ProfileExtractor:
    """Call the profile-extraction prompt and enforce a typed response contract."""

    def __init__(
        self,
        prompt_registry: PromptRegistry,
        model: Any,
        *,
        prompt_id: str = "profile_extractor",
        prompt_version: int | None = None,
    ) -> None:
        self.prompt_registry = prompt_registry
        self.model = model
        self.prompt_id = prompt_id
        self.prompt_version = prompt_version

    def analyze(self, user_profile: UserProfile, user_message: str) -> ProfileAnalysis:
        prompt = self.prompt_registry.get(self.prompt_id, self.prompt_version)
        rendered = prompt.render(
            {
                "user_profile": user_profile.model_dump_json(indent=2),
                "user_message": user_message,
            }
        )
        structured_model = self.model.with_structured_output(ProfileAnalysis)
        response = structured_model.invoke(rendered)
        return _validate_model_output(response, ProfileAnalysis)


def _validate_model_output(payload: Any, schema: type[BaseModel]) -> BaseModel:
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)
