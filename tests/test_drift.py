from __future__ import annotations

from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import Any

from mythinking.drift import DriftJudge, DriftResolver
from mythinking.prompts import PromptRegistry
from mythinking.state import (
    DriftAssessment,
    DriftJudgment,
    DriftSignal,
    DriftStatus,
    NorthStar,
    ProjectState,
    TangentDisposition,
)

PROMPT_DIR = Path(__file__).parents[1] / "prompts"

ON_TRACK_STATUSES = {"on_track", "no_drift", "stay_on_track"}
INSUFFICIENT_CONTEXT_STATUSES = {"insufficient_context", "needs_context", "context_missing"}
DRIFT_STATUSES = {"drift", "drifted", "off_track", "tangent", "off_goal"}
INSUFFICIENT_CONTEXT_DISPOSITIONS = {
    "insufficient_context",
    "not_enough_context",
    "needs_context",
    "context_missing",
}
PARKED_DISPOSITIONS = {"parked", "park", "parking_lot"}
MISSING_ANCHOR_SIGNALS = {"missing_anchor", "insufficient_context"}


def _normalize_semantic(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw).strip().lower().replace("-", "_").replace(" ", "_")


def _read_required_attr(instance: Any, *candidates: str) -> Any:
    for candidate in candidates:
        if hasattr(instance, candidate):
            return getattr(instance, candidate)
    raise AssertionError(
        f"Expected one of {candidates!r} on {type(instance).__name__}, found none."
    )


def _assessment_status(assessment: Any) -> str:
    return _normalize_semantic(_read_required_attr(assessment, "status", "drift_status"))


def _assessment_disposition(assessment: Any) -> str:
    return _normalize_semantic(
        _read_required_attr(assessment, "disposition", "recommended_disposition", "action")
    )


def _assessment_summary(assessment: Any) -> str:
    return str(
        _read_required_attr(
            assessment,
            "tangent_summary",
            "summary",
            "branch_summary",
        )
    ).strip()


def _assessment_branch_name(assessment: Any) -> str:
    return str(
        _read_required_attr(
            assessment,
            "branch_name",
            "suggested_branch_name",
            "tangent_branch_name",
            "name",
        )
    ).strip()


def _candidate_fields(model_type: type[Any]) -> set[str]:
    if hasattr(model_type, "model_fields"):
        return set(model_type.model_fields)
    if hasattr(model_type, "__dataclass_fields__"):
        return set(model_type.__dataclass_fields__)
    return set(getattr(model_type, "__annotations__", {}))


def _field_annotation(model_type: type[Any], field_name: str) -> Any:
    model_fields = getattr(model_type, "model_fields", None)
    if model_fields and field_name in model_fields:
        return model_fields[field_name].annotation
    return None


def _coerce_enum_value(annotation: Any, value: Any) -> Any:
    if not isinstance(annotation, type) or not issubclass(annotation, Enum):
        return value

    normalized = _normalize_semantic(value)
    for member in annotation:
        if _normalize_semantic(member) == normalized:
            return member

    semantic_aliases = {
        "drift": {"drift", "drifted", "off_track"},
        "on_track": {"on_track", "no_drift", "stay_on_track"},
        "branch": {"branch", "preserve_tangent"},
        "parked": {"parked", "park", "parking_lot"},
    }
    alias_matches = semantic_aliases.get(normalized)
    if alias_matches:
        for member in annotation:
            if _normalize_semantic(member) in alias_matches:
                return member

    return value


def _build_assessment(**semantic_values: Any) -> Any:
    drift_module = import_module("mythinking.drift")
    assessment_type = drift_module.DriftAssessment
    available_fields = _candidate_fields(assessment_type)
    field_aliases = {
        "status": ("status", "drift_status"),
        "disposition": ("disposition", "recommended_disposition", "action"),
        "signals": ("signals", "detected_signals"),
        "tangent_summary": ("tangent_summary", "summary", "branch_summary"),
        "branch_name": ("branch_name", "suggested_branch_name", "tangent_branch_name", "name"),
    }

    kwargs: dict[str, Any] = {}
    for semantic_name, value in semantic_values.items():
        for candidate in field_aliases[semantic_name]:
            if candidate in available_fields:
                kwargs[candidate] = _coerce_enum_value(
                    _field_annotation(assessment_type, candidate),
                    value,
                )
                break
        else:
            if semantic_name in {"status", "disposition"}:
                raise AssertionError(
                    f"{assessment_type.__name__} is missing a field for {semantic_name!r}."
                )

    return assessment_type(**kwargs)


def _create_detector() -> Any:
    drift_module = import_module("mythinking.drift")
    return drift_module.DriftDetector()


def _create_branch_manager() -> Any:
    branching_module = import_module("mythinking.branching")
    return branching_module.BranchManager()


def _anchored_project_state() -> ProjectState:
    return ProjectState(
        north_star=NorthStar(
            title="MyThinking",
            problem_statement="Solo builders lose the thread while shaping product ideas.",
            desired_outcome="Stay anchored to the core idea while saving useful tangents.",
            beneficiary="Solo builders",
            constraints=["Keep it local", "Stay deterministic before using a model"],
            success_criteria=["End each session with a next step"],
            non_goals=["General-purpose note taking"],
            current_hypothesis="A structured thinking partner can reduce drift.",
            next_action="Prototype the CLI flow.",
        )
    )


def _tangent_record_count(project_state: ProjectState) -> int:
    return len(project_state.branches) + len(project_state.parked_ideas)


def _contains_any(text: str, *needles: str) -> bool:
    normalized = text.lower()
    return any(needle in normalized for needle in needles)


def _assessment_signal_set(assessment: Any) -> set[str]:
    signals = _read_required_attr(assessment, "signals", "detected_signals")
    return {_normalize_semantic(signal) for signal in signals}


def test_assess_stays_on_track_when_context_is_too_thin_to_call_drift() -> None:
    detector = _create_detector()
    project_state = ProjectState(north_star=NorthStar(title="Early idea"))

    assessment = detector.assess(
        project_state,
        "Should I use a vector database for this?",
    )

    markers = {
        _assessment_status(assessment),
        _assessment_disposition(assessment),
        *_assessment_signal_set(assessment),
    }

    assert _assessment_status(assessment) not in DRIFT_STATUSES
    assert _assessment_status(assessment) in (ON_TRACK_STATUSES | INSUFFICIENT_CONTEXT_STATUSES)
    assert markers & (
        INSUFFICIENT_CONTEXT_STATUSES | INSUFFICIENT_CONTEXT_DISPOSITIONS | MISSING_ANCHOR_SIGNALS
    )


def test_assess_keeps_anchored_work_on_track() -> None:
    detector = _create_detector()

    assessment = detector.assess(
        _anchored_project_state(),
        "The first experiment should be a local CLI capture loop before any UI work.",
    )

    assert _assessment_status(assessment) in ON_TRACK_STATUSES


def test_assess_detects_research_tangent_and_preserves_summary_fields() -> None:
    detector = _create_detector()

    assessment = detector.assess(
        _anchored_project_state(),
        "By the way, teach me about vector databases and embeddings infrastructure.",
    )

    assert _assessment_status(assessment) in DRIFT_STATUSES
    assert _contains_any(_assessment_summary(assessment), "vector", "retrieval")
    assert _contains_any(_assessment_branch_name(assessment), "vector", "retrieval")


def test_assess_parking_language_maps_to_a_parked_disposition() -> None:
    detector = _create_detector()

    assessment = detector.assess(
        _anchored_project_state(),
        "Let's park this vector database question for later and get back to the user workflow.",
    )

    assert _assessment_disposition(assessment) in PARKED_DISPOSITIONS
    assert _contains_any(_assessment_summary(assessment), "vector", "database")


def test_preserve_tangent_is_idempotent_for_repeated_assessments() -> None:
    branch_manager = _create_branch_manager()
    initial_state = _anchored_project_state()
    assessment = _build_assessment(
        status="drift",
        disposition="branch",
        tangent_summary="Research vector database options separately from the core idea flow.",
        branch_name="Vector database research",
    )

    once = branch_manager.preserve_tangent(initial_state, assessment)
    twice = branch_manager.preserve_tangent(once, assessment)

    assert _tangent_record_count(once) == 1
    assert _tangent_record_count(twice) == 1
    if twice.branches:
        branch = twice.branches[0]
        assert _contains_any(branch.name, "vector")
        assert _contains_any(branch.summary, "vector", "database")
    else:
        assert len(twice.parked_ideas) == 1
        assert _contains_any(twice.parked_ideas[0], "vector")


def test_assess_returns_ambiguous_when_no_deterministic_signal_fires() -> None:
    detector = _create_detector()

    assessment = detector.assess(_anchored_project_state(), "Focus on the riskiest part first.")

    assert _assessment_status(assessment) not in ON_TRACK_STATUSES
    assert _assessment_status(assessment) not in DRIFT_STATUSES
    assert _assessment_status(assessment) == "ambiguous"


class FakeStructuredModel:
    def __init__(self, payload: dict[str, str]) -> None:
        self.payload = payload
        self.rendered_prompt = ""

    def invoke(self, rendered_prompt: str) -> dict[str, str]:
        self.rendered_prompt = rendered_prompt
        return self.payload


class FakeModel:
    def __init__(self, payload: dict[str, str]) -> None:
        self.structured_model = FakeStructuredModel(payload)

    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        return self.structured_model


def test_drift_resolver_leaves_ambiguous_status_unresolved_without_a_judge() -> None:
    resolver = DriftResolver(_create_detector(), None)

    assessment = resolver.assess(_anchored_project_state(), "Focus on the riskiest part first.")

    assert assessment.status is DriftStatus.AMBIGUOUS


def test_drift_resolver_does_not_call_the_judge_for_confident_assessments() -> None:
    class ExplodingJudge:
        def resolve(self, project_state, user_message, assessment):
            raise AssertionError("judge should not be called for confident assessments")

    resolver = DriftResolver(_create_detector(), ExplodingJudge())

    assessment = resolver.assess(
        _anchored_project_state(),
        "The first experiment should be a local CLI capture loop before any UI work.",
    )

    assert assessment.status is DriftStatus.ON_TRACK


def test_drift_judge_resolves_an_ambiguous_turn_to_drifted() -> None:
    model = FakeModel(
        {
            "status": "drifted",
            "disposition": "branch",
            "reason": "This introduces an unrelated topic.",
            "tangent_summary": "Focus on the riskiest part first",
            "branch_name": "Riskiest Part",
        }
    )
    judge = DriftJudge(PromptRegistry(PROMPT_DIR), model)
    ambiguous = DriftAssessment(status=DriftStatus.AMBIGUOUS, reason="inconclusive")

    resolved = judge.resolve(
        _anchored_project_state(),
        "Focus on the riskiest part first.",
        ambiguous,
    )

    assert resolved.status is DriftStatus.DRIFTED
    assert resolved.disposition is TangentDisposition.BRANCH
    assert resolved.tangent_summary == "Focus on the riskiest part first"
    assert resolved.branch_name == "Riskiest Part"
    assert DriftSignal.MODEL_FALLBACK in resolved.signals
    assert "riskiest part" in model.structured_model.rendered_prompt.lower()


def test_drift_judge_defaults_to_on_track_when_status_is_not_drifted() -> None:
    model = FakeModel({"status": "ambiguous", "reason": "Unclear either way."})
    judge = DriftJudge(PromptRegistry(PROMPT_DIR), model)
    ambiguous = DriftAssessment(status=DriftStatus.AMBIGUOUS, reason="inconclusive")

    resolved = judge.resolve(_anchored_project_state(), "Not sure what this is.", ambiguous)

    assert resolved.status is DriftStatus.ON_TRACK
    assert DriftSignal.MODEL_FALLBACK in resolved.signals


def test_drift_judgment_schema_defaults() -> None:
    judgment = DriftJudgment()

    assert judgment.status is DriftStatus.ON_TRACK
    assert judgment.disposition is TangentDisposition.NONE
