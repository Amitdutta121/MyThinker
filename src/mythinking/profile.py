"""Merge extracted user-profile updates and render the profile for prompts."""

from mythinking.state import ProfileAnalysis, UserProfile


class ProfileService:
    """Write Profile Extractor updates into the persisted user profile."""

    def merge(self, profile: UserProfile, analysis: ProfileAnalysis) -> UserProfile:
        updated = profile.model_copy(deep=True)
        update = analysis.profile_update

        if update.role is not None:
            role = update.role.strip()
            if role:
                updated.role = role

        updated.expertise = _append_unique(updated.expertise, update.expertise_to_add)
        updated.working_style = _append_unique(updated.working_style, update.working_style_to_add)
        return updated


def format_profile(profile: UserProfile) -> str:
    """Render the user profile as a readable block, e.g. for `mythinking profile`.

    Not yet wired into the supervisor prompt -- see the M6c handoff's Open
    issues for why that's deliberately deferred to a follow-up slice.
    """

    if not profile.role and not profile.expertise and not profile.working_style:
        return "No user profile captured yet."

    lines: list[str] = []
    if profile.role:
        lines.append(f"Role: {profile.role}")
    if profile.expertise:
        lines.append("Expertise: " + ", ".join(profile.expertise))
    if profile.working_style:
        lines.append("Working style: " + ", ".join(profile.working_style))
    return "\n".join(lines)


def _append_unique(existing: list[str], additions: list[str]) -> list[str]:
    merged = list(existing)
    seen = {_normalize(item) for item in merged}
    for item in additions:
        cleaned = item.strip()
        key = _normalize(cleaned)
        if cleaned and key not in seen:
            merged.append(cleaned)
            seen.add(key)
    return merged


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())
