"""Semantic + lexical gates that guard state-changing thinking tools.

These are deliberately small: a deterministic regex check for commitment
authorization, plus three single-shot structured-output LLM calls that decide
whether a proposed North Star / decision / evidence item is actually supported
by the current turn. Tool contracts call these before mutating `ProjectState`
so a bad tool choice fails safe instead of corrupting the board.
"""

import re
from typing import Any

from pydantic import BaseModel

_COMMIT_PATTERNS = (
    r"\blet'?s (?:go with|use|choose|select|commit to|switch to)\b",
    r"\bgo with (?:that|it|this|the recommendation|the proposed direction|the proposal)\b",
    r"\bi (?:choose|select|accept|want|prefer|approve)\b",
    r"\bcommit (?:it|that|this|the direction|the recommendation|the proposal)\b",
    r"\brecord (?:that|this|it) as (?:our|the) direction\b",
    r"\bmake (?:that|this|it) (?:our|the) direction\b",
    r"\b(?:choose|decide) (?:the best|the strongest|for me|for us|which)\b"
    r".*\b(?:commit|record|go)\b",
    r"\bthat'?s our direction\b",
)


def user_authorized_commitment(user_message: str) -> bool:
    """True only when the current turn explicitly accepts/commits a direction."""
    text = user_message.lower().strip()
    return any(re.search(pattern, text) for pattern in _COMMIT_PATTERNS)


class NorthStarGate(BaseModel):
    supported: bool = False
    normalized_goal: str = ""
    reason: str = ""


class DecisionGate(BaseModel):
    supported_by_user_message: bool = False
    reason: str = ""


class EvidenceGate(BaseModel):
    supported_by_excerpt: bool = False
    project_relevant: bool = False
    support_reason: str = ""
    relevance_reason: str = ""


def check_north_star_proposal(model: Any, user_message: str, proposed_goal: str) -> NorthStarGate:
    prompt = f"""Decide whether PROPOSED GOAL is clearly stated by the CURRENT USER MESSAGE.
Do not infer a project from a generic question or an ambiguous request.

CURRENT USER MESSAGE:
{user_message}

PROPOSED GOAL:
{proposed_goal}

supported=true only if the user has actually communicated this project/goal in the
current message. normalized_goal should be concise but preserve the user's meaning.
"""
    return _invoke(model, NorthStarGate, prompt)


def check_user_decision(model: Any, user_message: str, statement: str) -> DecisionGate:
    prompt = f"""Does the CURRENT USER MESSAGE explicitly make, accept, or ask to record this
decision? A recommendation made by the assistant is not, by itself, a user decision.

CURRENT USER MESSAGE:
{user_message}

PROPOSED DECISION:
{statement}
"""
    return _invoke(model, DecisionGate, prompt)


def check_evidence(
    model: Any,
    north_star: str,
    committed_direction: str,
    claim: str,
    source_excerpt: str,
) -> EvidenceGate:
    prompt = f"""Evaluate a candidate project evidence item.

NORTH STAR:
{north_star}

COMMITTED DIRECTION:
{committed_direction or "(none)"}

CLAIM:
{claim}

SOURCE EXCERPT:
{source_excerpt}

supported_by_excerpt=true only if the excerpt actually supports the claim.
project_relevant=true only if the claim materially informs the North Star or the
committed direction -- not merely because it shares generic topic words.
"""
    return _invoke(model, EvidenceGate, prompt)


def _invoke(model: Any, schema: type[BaseModel], prompt: str) -> Any:
    payload = model.with_structured_output(schema).invoke(prompt)
    if isinstance(payload, schema):
        return payload
    return schema.model_validate(payload)
