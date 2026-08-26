"""Deterministic drift detection for keeping turns anchored to the North Star."""

from __future__ import annotations

import re
from collections.abc import Iterable

from mythinking.state import (
    DriftAssessment,
    DriftSignal,
    DriftStatus,
    ProjectState,
    TangentDisposition,
)

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "help",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "so",
    "that",
    "the",
    "this",
    "through",
    "to",
    "us",
    "want",
    "we",
    "what",
    "with",
    "you",
    "your",
}

_TANGENT_PHRASES = (
    "another idea",
    "by the way",
    "different topic",
    "off topic",
    "separate topic",
    "side note",
    "tangent",
    "unrelated",
)

_PARKING_PHRASES = (
    "come back later",
    "park this",
    "parking lot",
    "save for later",
    "table this",
)

_TOPIC_SHIFT_PHRASES = (
    "explain",
    "teach me about",
    "tell me about",
    "tell me everything about",
    "what do you know about",
)


class DriftDetector:
    """Classify whether a turn is still anchored to the current project frame."""

    def assess(self, project_state: ProjectState, user_message: str) -> DriftAssessment:
        message = user_message.strip()
        if not _has_sufficient_anchor_context(project_state):
            return DriftAssessment(
                status=DriftStatus.INSUFFICIENT_CONTEXT,
                reason="The North Star is not specific enough to judge drift yet.",
                signals=[DriftSignal.MISSING_ANCHOR],
            )
        anchor_terms = _anchor_terms(project_state)

        lowered = _normalize_text(message)
        message_terms = _tokenize(message)
        overlap = anchor_terms & message_terms
        explicit_tangent = any(phrase in lowered for phrase in _TANGENT_PHRASES)
        parking_language = any(phrase in lowered for phrase in _PARKING_PHRASES) or (
            "later" in message_terms and any(token in message_terms for token in {"park", "save"})
        )
        topic_shift = any(phrase in lowered for phrase in _TOPIC_SHIFT_PHRASES)

        if overlap and not explicit_tangent and not parking_language:
            return DriftAssessment(
                status=DriftStatus.ON_TRACK,
                reason="The message still overlaps with the active North Star.",
            )

        if explicit_tangent or parking_language or (topic_shift and not overlap):
            signals: list[DriftSignal] = []
            if not overlap:
                signals.append(DriftSignal.LOW_ANCHOR_OVERLAP)
            if explicit_tangent:
                signals.append(DriftSignal.EXPLICIT_TANGENT)
            if parking_language:
                signals.append(DriftSignal.PARKING_LANGUAGE)

            tangent_summary = _summarize_tangent(message)
            disposition = (
                TangentDisposition.PARKED if parking_language else TangentDisposition.BRANCH
            )
            return DriftAssessment(
                status=DriftStatus.DRIFTED,
                disposition=disposition,
                reason=(
                    "The message appears to open a side topic that does not "
                    "match the current North Star."
                ),
                tangent_summary=tangent_summary,
                branch_name=_branch_name(tangent_summary),
                signals=signals,
            )

        return DriftAssessment(
            status=DriftStatus.ON_TRACK,
            reason="No deterministic drift signal was strong enough to interrupt the main thread.",
        )


def _anchor_terms(project_state: ProjectState) -> set[str]:
    north_star = project_state.north_star
    values: list[str] = [
        north_star.title,
        north_star.problem_statement,
        north_star.desired_outcome,
        north_star.beneficiary,
        north_star.current_hypothesis,
        north_star.next_action,
        *north_star.constraints,
        *north_star.success_criteria,
        *north_star.non_goals,
        *project_state.open_questions,
    ]
    return {
        token for token in _tokenize_many(values) if token not in _STOP_WORDS and len(token) > 2
    }


def _has_sufficient_anchor_context(project_state: ProjectState) -> bool:
    north_star = project_state.north_star
    return all(
        field.strip()
        for field in (
            north_star.problem_statement,
            north_star.desired_outcome,
            north_star.beneficiary,
        )
    )


def _tokenize_many(values: Iterable[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        tokens.update(_tokenize(value))
    return tokens


def _tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if token not in _STOP_WORDS}


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def _summarize_tangent(message: str) -> str:
    cleaned = " ".join(message.split()).strip(" .?!")
    if not cleaned:
        return ""
    if len(cleaned) <= 120:
        return cleaned
    return cleaned[:117].rstrip() + "..."


def _branch_name(summary: str) -> str:
    words = [
        word for word in re.findall(r"[A-Za-z0-9]+", summary) if word.lower() not in _STOP_WORDS
    ]
    if not words:
        return "Preserved tangent"
    return " ".join(words[:4]).title()
