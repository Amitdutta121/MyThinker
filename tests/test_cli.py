import sys
from pathlib import Path

import pytest

from mythinking import cli
from mythinking.config import Settings
from mythinking.persistence import StateRepository
from mythinking.state import AssistantTurn, NorthStar, ProjectState, ThinkingMode


def test_build_parser_parses_chat_command() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["chat", "clarify this idea", "--project-id", "proj-123"])

    assert args.command == "chat"
    assert args.message == "clarify this idea"
    assert args.project_id == "proj-123"
    assert args.last is False


def test_build_parser_parses_chat_last_flag() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["chat", "keep going", "--last"])

    assert args.last is True
    assert args.project_id is None


def test_build_parser_rejects_project_id_and_last_together() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["chat", "x", "--project-id", "p1", "--last"])


def test_build_parser_parses_serve_command_with_defaults() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["serve"])

    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_build_parser_parses_serve_command_with_overrides() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["serve", "--host", "0.0.0.0", "--port", "9001"])

    assert args.host == "0.0.0.0"
    assert args.port == 9001


def test_run_serve_delegates_to_uvicorn(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    class FakeUvicorn:
        @staticmethod
        def run(app: str, host: str, port: int) -> None:
            calls.append((app, host, port))

    monkeypatch.setitem(sys.modules, "uvicorn", FakeUvicorn)

    exit_code = cli.run_serve(host="0.0.0.0", port=9001)

    assert exit_code == 0
    assert calls == [("mythinking.api:app", "0.0.0.0", 9001)]


def test_main_routes_serve_command_to_run_serve(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        cli, "run_serve", lambda host="127.0.0.1", port=8000: calls.append((host, port)) or 0
    )

    exit_code = cli.main(["serve", "--port", "9001"])

    assert exit_code == 0
    assert calls == [("127.0.0.1", 9001)]


def test_build_parser_parses_list_and_show_commands() -> None:
    parser = cli.build_parser()

    list_args = parser.parse_args(["list", "--limit", "5"])
    show_args = parser.parse_args(["show", "proj-123"])
    show_default_args = parser.parse_args(["show"])

    assert list_args.command == "list"
    assert list_args.limit == 5
    assert show_args.project_id == "proj-123"
    assert show_default_args.project_id is None


def test_run_chat_uses_runtime_and_prints_turn(monkeypatch, capsys) -> None:
    calls: list[tuple[str, str | None]] = []

    class FakeRuntime:
        def run_turn(self, user_message: str, project_id: str | None = None) -> AssistantTurn:
            calls.append((user_message, project_id))
            return AssistantTurn(
                project_id="proj-123",
                mode=ThinkingMode.CLARIFY,
                message="Need a narrower decision.\n\nWhat outcome matters most?",
                question="What outcome matters most?",
            )

    monkeypatch.setattr(cli, "ThinkingRuntime", FakeRuntime)

    exit_code = cli.run_chat("Need help", project_id="proj-123")
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [("Need help", "proj-123")]
    assert "Project ID: proj-123" in output
    assert "Mode: clarify" in output
    assert "What outcome matters most?" in output


def test_run_chat_resolves_last_project_when_requested(monkeypatch, capsys, tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", prompt_dir=tmp_path / "prompts")
    repository = StateRepository(settings.state_database_path)
    existing = ProjectState(north_star=NorthStar(title="Existing idea"))
    repository.save(existing)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    calls: list[tuple[str, str | None]] = []

    class FakeRuntime:
        def run_turn(self, user_message: str, project_id: str | None = None) -> AssistantTurn:
            calls.append((user_message, project_id))
            return AssistantTurn(
                project_id=project_id or "unexpected",
                mode=ThinkingMode.CAPTURE,
                message="ok",
            )

    monkeypatch.setattr(cli, "ThinkingRuntime", FakeRuntime)

    exit_code = cli.run_chat("continue", resume_last=True)

    assert exit_code == 0
    assert calls == [("continue", existing.project_id)]


def test_run_chat_starts_new_project_when_no_previous_session(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", prompt_dir=tmp_path / "prompts")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    calls: list[tuple[str, str | None]] = []

    class FakeRuntime:
        def run_turn(self, user_message: str, project_id: str | None = None) -> AssistantTurn:
            calls.append((user_message, project_id))
            return AssistantTurn(project_id="new-proj", mode=ThinkingMode.CAPTURE, message="ok")

    monkeypatch.setattr(cli, "ThinkingRuntime", FakeRuntime)

    exit_code = cli.run_chat("start", resume_last=True)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == [("start", None)]
    assert "No previous thinking project to resume" in output


def test_run_list_prints_recent_projects(monkeypatch, capsys, tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", prompt_dir=tmp_path / "prompts")
    repository = StateRepository(settings.state_database_path)
    repository.save(ProjectState(north_star=NorthStar(title="Idea one")))
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    exit_code = cli.run_list(limit=5)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Idea one" in output


def test_run_list_prints_message_when_no_projects(monkeypatch, capsys, tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", prompt_dir=tmp_path / "prompts")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    exit_code = cli.run_list()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No thinking projects yet" in output


def test_run_show_prints_summary_for_latest_project_by_default(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", prompt_dir=tmp_path / "prompts")
    repository = StateRepository(settings.state_database_path)
    state = ProjectState(north_star=NorthStar(title="Resumable idea"))
    repository.save(state)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    exit_code = cli.run_show()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert state.project_id in output
    assert "Resumable idea" in output


def test_run_show_reports_unknown_project(monkeypatch, capsys, tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path / "data", prompt_dir=tmp_path / "prompts")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    exit_code = cli.run_show("missing")
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "Unknown project_id" in output


def test_main_routes_chat_command_to_run_chat(monkeypatch) -> None:
    calls: list[tuple[str, str | None, bool]] = []

    def fake_run_chat(
        message: str, project_id: str | None = None, resume_last: bool = False
    ) -> int:
        calls.append((message, project_id, resume_last))
        return 17

    monkeypatch.setattr(cli, "run_chat", fake_run_chat)

    exit_code = cli.main(["chat", "Map the decision", "--project-id", "proj-9"])

    assert exit_code == 17
    assert calls == [("Map the decision", "proj-9", False)]


def test_main_routes_list_and_show_commands(monkeypatch) -> None:
    list_calls: list[int] = []
    show_calls: list[str | None] = []
    monkeypatch.setattr(cli, "run_list", lambda limit=10: list_calls.append(limit) or 0)
    monkeypatch.setattr(cli, "run_show", lambda project_id=None: show_calls.append(project_id) or 0)

    cli.main(["list", "--limit", "3"])
    cli.main(["show", "proj-1"])

    assert list_calls == [3]
    assert show_calls == ["proj-1"]
