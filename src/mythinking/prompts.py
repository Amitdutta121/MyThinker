"""Versioned prompt specifications with evidence and evaluation metadata."""

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl


class PromptEvidence(BaseModel):
    source_url: HttpUrl
    supports: str
    product_hypothesis: bool = False


class PromptSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: int = Field(ge=1)
    purpose: str = Field(min_length=1)
    template: str = Field(min_length=1)
    evidence: list[PromptEvidence] = Field(min_length=1)
    eval_datasets: list[str] = Field(min_length=1)
    success_metrics: list[str] = Field(min_length=1)

    @property
    def key(self) -> str:
        return f"{self.id}:v{self.version}"

    def render(self, context: Mapping[str, str]) -> str:
        try:
            return self.template.format_map(context)
        except KeyError as error:
            raise ValueError(f"Missing prompt variable: {error.args[0]}") from error


def load_prompt(path: Path) -> PromptSpec:
    with path.open(encoding="utf-8") as prompt_file:
        payload = yaml.safe_load(prompt_file)
    return PromptSpec.model_validate(payload)


class PromptRegistry:
    def __init__(self, prompt_dir: Path) -> None:
        self.prompt_dir = prompt_dir

    def load_all(self) -> dict[str, PromptSpec]:
        prompts = [load_prompt(path) for path in sorted(self.prompt_dir.glob("*.yaml"))]
        registry = {prompt.key: prompt for prompt in prompts}
        if len(registry) != len(prompts):
            raise ValueError("Duplicate prompt id and version")
        return registry

    def get(self, prompt_id: str, version: int | None = None) -> PromptSpec:
        prompts = self.load_all()
        candidates = [prompt for prompt in prompts.values() if prompt.id == prompt_id]
        if not candidates:
            raise KeyError(f"Unknown prompt: {prompt_id}")
        if version is not None:
            key = f"{prompt_id}:v{version}"
            if key not in prompts:
                raise KeyError(f"Unknown prompt version: {key}")
            return prompts[key]
        return max(candidates, key=lambda prompt: prompt.version)
