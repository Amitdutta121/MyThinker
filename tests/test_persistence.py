from pathlib import Path

from mythinking.persistence import StateRepository
from mythinking.state import NorthStar, ProjectState


def test_state_repository_round_trip(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    state = ProjectState(north_star=NorthStar(title="Thinking partner"))

    repository.save(state)
    loaded = repository.load(state.project_id)

    assert loaded is not None
    assert loaded.project_id == state.project_id
    assert loaded.north_star.title == "Thinking partner"
    assert repository.list_project_ids() == [state.project_id]


def test_state_repository_delete(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    state = ProjectState()
    repository.save(state)

    assert repository.delete(state.project_id)
    assert repository.load(state.project_id) is None
    assert not repository.delete(state.project_id)
