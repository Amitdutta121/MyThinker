import pytest
from pydantic import ValidationError

from mythinking.state import IdeaBranch, NorthStar, ProjectState, ThinkingMode


def test_project_state_json_round_trip() -> None:
    branch = IdeaBranch(name="Voice interface")
    state = ProjectState(
        north_star=NorthStar(title="Thinking partner"),
        current_mode=ThinkingMode.EXPLORE,
        active_branch_id=branch.id,
        branches=[branch],
    )

    restored = ProjectState.model_validate_json(state.model_dump_json())

    assert restored == state
    assert restored.active_branch_id == branch.id


def test_active_branch_must_reference_existing_branch() -> None:
    with pytest.raises(ValidationError, match="active_branch_id"):
        ProjectState(active_branch_id="missing")
