from mythinking.profile import ProfileService, format_profile
from mythinking.state import ProfileAnalysis, UserProfile, UserProfileUpdate


def test_merge_sets_role_and_appends_unique_expertise_and_working_style() -> None:
    service = ProfileService()
    profile = UserProfile()
    analysis = ProfileAnalysis(
        profile_update=UserProfileUpdate(
            role="Backend engineer",
            expertise_to_add=["Distributed systems", "distributed systems"],
            working_style_to_add=["Thinks out loud"],
        )
    )

    updated = service.merge(profile, analysis)

    assert updated.role == "Backend engineer"
    assert updated.expertise == ["Distributed systems"]
    assert updated.working_style == ["Thinks out loud"]


def test_merge_ignores_a_blank_role() -> None:
    service = ProfileService()
    profile = UserProfile(role="Backend engineer")
    analysis = ProfileAnalysis(profile_update=UserProfileUpdate(role="   "))

    updated = service.merge(profile, analysis)

    assert updated.role == "Backend engineer"


def test_merge_dedupes_expertise_against_existing_entries() -> None:
    service = ProfileService()
    profile = UserProfile(expertise=["Distributed systems"])
    analysis = ProfileAnalysis(
        profile_update=UserProfileUpdate(expertise_to_add=["distributed systems"])
    )

    updated = service.merge(profile, analysis)

    assert updated.expertise == ["Distributed systems"]


def test_format_profile_reports_none_when_empty() -> None:
    assert format_profile(UserProfile()) == "No user profile captured yet."


def test_format_profile_renders_populated_fields() -> None:
    profile = UserProfile(
        role="Backend engineer",
        expertise=["Distributed systems"],
        working_style=["Thinks out loud"],
    )

    rendered = format_profile(profile)

    assert "Role: Backend engineer" in rendered
    assert "Expertise: Distributed systems" in rendered
    assert "Working style: Thinks out loud" in rendered
