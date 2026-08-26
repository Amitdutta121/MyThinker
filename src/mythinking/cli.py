"""Small local commands for setup diagnostics and provider smoke testing."""

import argparse
from collections.abc import Sequence

from mythinking.config import get_settings
from mythinking.llm import create_chat_model
from mythinking.persistence import StateRepository
from mythinking.prompts import PromptRegistry
from mythinking.runtime import ThinkingRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mythinking")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Initialize local application storage")
    subparsers.add_parser("status", help="Show non-secret runtime configuration")
    subparsers.add_parser("smoke-model", help="Make one small live OpenRouter request")
    chat_parser = subparsers.add_parser(
        "chat",
        help="Run one persisted thinking turn",
    )
    chat_parser.add_argument("message", help="The user message to process")
    chat_parser.add_argument(
        "--project-id",
        help="Resume an existing thinking project by id",
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


def run_chat(message: str, project_id: str | None = None) -> int:
    turn = ThinkingRuntime().run_turn(message, project_id=project_id)
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
        "chat": lambda: run_chat(args.message, project_id=args.project_id),
    }
    return commands[args.command]()
