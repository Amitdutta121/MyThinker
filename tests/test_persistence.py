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


def test_state_repository_list_recent_orders_newest_first(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    older = ProjectState(north_star=NorthStar(title="Older idea"))
    newer = ProjectState(north_star=NorthStar(title="Newer idea"))
    repository.save(older)
    repository.save(newer)

    recent = repository.list_recent()

    assert [state.project_id for state in recent] == [newer.project_id, older.project_id]
    assert repository.latest_project_id() == newer.project_id


def test_state_repository_list_recent_respects_limit(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    for _ in range(3):
        repository.save(ProjectState())

    assert len(repository.list_recent(limit=2)) == 2


def test_state_repository_latest_project_id_is_none_when_empty(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")

    assert repository.latest_project_id() is None


def test_state_repository_delete(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.sqlite")
    state = ProjectState()
    repository.save(state)

    assert repository.delete(state.project_id)
    assert repository.load(state.project_id) is None
    assert not repository.delete(state.project_id)
