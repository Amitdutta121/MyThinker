from mythinking import cli
from mythinking.state import AssistantTurn, ThinkingMode


def test_build_parser_parses_chat_command() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["chat", "clarify this idea", "--project-id", "proj-123"])

    assert args.command == "chat"
    assert args.message == "clarify this idea"
    assert args.project_id == "proj-123"


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


def test_main_routes_chat_command_to_run_chat(monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_run_chat(message: str, project_id: str | None = None) -> int:
        calls.append((message, project_id))
        return 17

    monkeypatch.setattr(cli, "run_chat", fake_run_chat)

    exit_code = cli.main(["chat", "Map the decision", "--project-id", "proj-9"])

    assert exit_code == 17
    assert calls == [("Map the decision", "proj-9")]
