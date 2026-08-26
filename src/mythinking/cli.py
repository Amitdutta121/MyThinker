"""Small local commands for setup diagnostics and provider smoke testing."""

import argparse
from collections.abc import Sequence

from mythinking.config import get_settings
from mythinking.llm import create_chat_model
from mythinking.persistence import StateRepository
from mythinking.prompts import PromptRegistry
from mythinking.runtime import ThinkingRuntime
from mythinking.summary import format_project_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mythinking")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Initialize local application storage")
    subparsers.add_parser("status", help="Show non-secret runtime configuration")
    subparsers.add_parser("smoke-model", help="Make one small live OpenRouter request")

    list_parser = subparsers.add_parser("list", help="List recent thinking projects")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of projects to show (default: 10)",
    )

    show_parser = subparsers.add_parser("show", help="Show a session summary for a project")
    show_parser.add_argument(
        "project_id",
        nargs="?",
        default=None,
        help="Project id to show; defaults to the most recently updated project",
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="Run one persisted thinking turn",
    )
    chat_parser.add_argument("message", help="The user message to process")
    chat_target = chat_parser.add_mutually_exclusive_group()
    chat_target.add_argument(
        "--project-id",
        help="Resume an existing thinking project by id",
    )
    chat_target.add_argument(
        "--last",
        action="store_true",
        help="Resume the most recently updated thinking project",
    )
    return parser


def run_init() -> int:
    settings = get_settings()
    StateRepository(settings.state_database_path).initialize()
    settings.checkpoint_database_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Initialized local storage in {settings.data_dir.resolve()}")
    return 0


def run_status() -> int:
    settings = get_settings()
    prompts = PromptRegistry(settings.prompt_dir).load_all()
    print(f"OpenRouter key configured: {settings.has_api_key}")
    print(f"OpenRouter model: {settings.openrouter_model}")
    print(f"Provider data collection: {settings.openrouter_data_collection}")
    print(f"Data directory: {settings.data_dir.resolve()}")
    print(f"Loaded prompt versions: {len(prompts)}")
    return 0


def run_smoke_model() -> int:
    response = create_chat_model(temperature=0, max_tokens=16).invoke(
        "Reply with exactly: OPENROUTER_OK"
    )
    print(response.text)
    return 0


def run_list(limit: int = 10) -> int:
    settings = get_settings()
    repository = StateRepository(settings.state_database_path)
    projects = repository.list_recent(limit)
    if not projects:
        print('No thinking projects yet. Start one with `mythinking chat "..."`.')
        return 0
    for project in projects:
        print(
            f"{project.project_id}  {project.updated_at.isoformat()}  "
            f"{project.current_mode.value:<8}  {project.north_star.title}"
        )
    return 0


def run_show(project_id: str | None = None) -> int:
    settings = get_settings()
    repository = StateRepository(settings.state_database_path)
    resolved_project_id = project_id or repository.latest_project_id()
    if resolved_project_id is None:
        print('No thinking projects yet. Start one with `mythinking chat "..."`.')
        return 1
    project_state = repository.load(resolved_project_id)
    if project_state is None:
        print(f"Unknown project_id: {resolved_project_id}")
        return 1
    print(format_project_summary(project_state))
    return 0


def run_chat(message: str, project_id: str | None = None, resume_last: bool = False) -> int:
    resolved_project_id = project_id
    if resume_last and resolved_project_id is None:
        settings = get_settings()
        resolved_project_id = StateRepository(settings.state_database_path).latest_project_id()
        if resolved_project_id is None:
            print("No previous thinking project to resume; starting a new one.")
    turn = ThinkingRuntime().run_turn(message, project_id=resolved_project_id)
    print(f"Project ID: {turn.project_id}")
    print(f"Mode: {turn.mode}")
    print()
    print(turn.message)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    commands = {
        "init": run_init,
        "status": run_status,
        "smoke-model": run_smoke_model,
        "list": lambda: run_list(args.limit),
        "show": lambda: run_show(args.project_id),
        "chat": lambda: run_chat(args.message, project_id=args.project_id, resume_last=args.last),
    }
    return commands[args.command]()
