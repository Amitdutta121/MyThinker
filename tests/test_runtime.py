"""Facade tests for the single-agent ThinkingRuntime.

The agent loop itself is stubbed (`build_thinker` is monkeypatched to a fake
agent). These tests pin the runtime's contract: state load/resume, persistence,
display-mode derivation, streaming shape, eager validation, and profile wiring.
"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import SecretStr

from mythinking.agents.profile_extractor import ProfileExtractor
from mythinking.config import Settings
from mythinking.runtime import ThinkingRuntime, _history_from_messages, create_runtime
from mythinking.state import (
    DirectionProposal,
    FrameAnalysis,
    NextAction,
    NorthStar,
    ProfileAnalysis,
    ProjectState,
    ThinkingMode,
    TurnStreamEventType,
    UserProfile,
    UserProfileUpdate,
)


class _FakeAgent:
    """Stands in for the compiled Thinker agent.

    `mutate` receives the live `holder` so a test can simulate a tool changing
    the board; `tool_names` are surfaced as ToolMessage names when streaming.
    """

    def __init__(self, holder, *, text: str, mutate=None, tool_names=(), token_chunks=()) -> None:
        self._holder = holder
        self._text = text
        self._mutate = mutate
        self._tool_names = tool_names
        self._token_chunks = token_chunks

    def invoke(self, _payload, config=None):
        if self._mutate:
            self._mutate(self._holder)
        return {"messages": [AIMessage(content=self._text)]}

    def stream(self, _payload, config=None, stream_mode=None):
        """Mirror LangGraph's multi-mode stream: yields ``(mode, chunk)`` pairs
        when ``stream_mode`` is a list (as the runtime now asks)."""
        if self._mutate:
            self._mutate(self._holder)
        multi = isinstance(stream_mode, (list, tuple))
        for name in self._tool_names:
            update = {
                "tools": {"messages": [ToolMessage(content="ok", name=name, tool_call_id=name)]}
            }
            yield ("updates", update) if multi else update
        if multi:
            for chunk in self._token_chunks:
                yield ("messages", (AIMessage(content=chunk), {"langgraph_node": "model"}))
        yield (
            ("updates", {"model": {"messages": [AIMessage(content=self._text)]}})
            if multi
            else {"model": {"messages": [AIMessage(content=self._text)]}}
        )


def _install_fake_agent(
    monkeypatch, *, text="Here's my take.", mutate=None, tool_names=(), token_chunks=()
):
    def _factory(model, tools, system_prompt, holder, *, checkpointer=None, **_kw):
        return _FakeAgent(
            holder, text=text, mutate=mutate, tool_names=tool_names, token_chunks=token_chunks
        )

    monkeypatch.setattr("mythinking.runtime.build_thinker", _factory)


class _StubProfileExtractor:
    def __init__(self, analysis: ProfileAnalysis) -> None:
        self.analysis = analysis
        self.calls: list[str] = []

    def analyze(self, _profile: UserProfile, user_message: str) -> ProfileAnalysis:
        self.calls.append(user_message)
        return self.analysis


def _build_runtime(tmp_path: Path, **overrides) -> ThinkingRuntime:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        prompt_dir=Path("prompts"),
        enable_profile_extraction=overrides.pop("enable_profile_extraction", False),
    )
    kwargs = dict(
        settings=settings,
        agent_model=object(),
        gate_model=object(),
        frame_analyst=object(),
        explorer=object(),
        synthesizer=object(),
        planner=object(),
        evidence_analyst=object(),
        store=None,
        context_retriever=None,
    )
    kwargs.update(overrides)
    return ThinkingRuntime(**kwargs)


def test_run_turn_persists_a_new_project(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch, text="Noted.")
    runtime = _build_runtime(tmp_path)

    turn = runtime.run_turn("  Help me think about a note-taking app  ")
    saved = runtime.get_project_state(turn.project_id)

    assert turn.message == "Noted."
    assert turn.mode is ThinkingMode.CLARIFY  # unframed goal
    assert saved is not None
    assert saved.project_id == turn.project_id


def test_run_turn_resumes_existing_project_by_id(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch)
    runtime = _build_runtime(tmp_path)

    first = runtime.run_turn("start here")
    second = runtime.run_turn("keep going", project_id=first.project_id)

    assert second.project_id == first.project_id


def test_run_turn_applies_and_persists_a_tool_style_mutation(tmp_path: Path, monkeypatch) -> None:
    def mutate(holder):
        ns = holder.project_state.north_star
        ns.problem_statement = "Ideas get lost mid-conversation"
        ns.desired_outcome = "Keep the main idea visible"
        ns.beneficiary = "Solo thinkers"

    _install_fake_agent(monkeypatch, mutate=mutate)
    runtime = _build_runtime(tmp_path)

    turn = runtime.run_turn("I want to build a thinking workspace.")
    saved = runtime.get_project_state(turn.project_id)

    assert saved is not None
    assert saved.north_star.problem_statement == "Ideas get lost mid-conversation"
    assert turn.mode is ThinkingMode.CAPTURE  # framed, no branches/proposal/plan


def test_run_turn_rejects_blank_message(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch)
    runtime = _build_runtime(tmp_path)
    with pytest.raises(ValueError, match="must not be blank"):
        runtime.run_turn("   ")


def test_run_turn_rejects_unknown_project_id(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch)
    runtime = _build_runtime(tmp_path)
    with pytest.raises(KeyError, match="Unknown project_id"):
        runtime.run_turn("resume", project_id="missing")


def test_get_project_state_returns_none_for_unknown_project(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch)
    runtime = _build_runtime(tmp_path)
    assert runtime.get_project_state("nope") is None


def test_history_from_messages_keeps_only_user_and_final_assistant_turns() -> None:
    raw = [
        SystemMessage(content="you are the thinker"),
        HumanMessage(content="  help me frame this  "),
        AIMessage(content="", tool_calls=[{"name": "set_north_star", "args": {}, "id": "t1"}]),
        ToolMessage(content="ok", name="set_north_star", tool_call_id="t1"),
        AIMessage(content="Here's the frame."),
        HumanMessage(content=""),
    ]

    history = _history_from_messages(raw)

    assert [(m.role.value, m.content) for m in history] == [
        ("user", "help me frame this"),
        ("assistant", "Here's the frame."),
    ]


def test_get_history_rejects_unknown_project(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch)
    runtime = _build_runtime(tmp_path)
    with pytest.raises(KeyError, match="Unknown project_id"):
        runtime.get_history("missing")


def test_get_history_is_empty_when_no_checkpoint_exists(tmp_path: Path, monkeypatch) -> None:
    # The fake agent never writes to the checkpointer, so a persisted project
    # has state but no transcript -- get_history must return [] rather than raise.
    _install_fake_agent(monkeypatch)
    runtime = _build_runtime(tmp_path)
    project_id = runtime.run_turn("seed the board").project_id
    assert runtime.get_history(project_id) == []


def test_stream_turn_emits_tool_node_events_then_one_turn_event(
    tmp_path: Path, monkeypatch
) -> None:
    _install_fake_agent(
        monkeypatch,
        text="Explored.",
        tool_names=("set_north_star", "explore_ideas"),
        token_chunks=("Explo", "red."),
    )
    runtime = _build_runtime(tmp_path)

    events = list(runtime.stream_turn("Explore designs for a thinking workspace"))

    node_names = [e.node for e in events if e.type is TurnStreamEventType.NODE]
    token_text = "".join(e.detail for e in events if e.type is TurnStreamEventType.TOKEN)
    turn_events = [e for e in events if e.type is TurnStreamEventType.TURN]
    assert node_names == ["set_north_star", "explore_ideas"]
    assert token_text == "Explored."
    assert len(turn_events) == 1
    assert turn_events[0].turn is not None
    assert turn_events[0].turn.message == "Explored."
    assert runtime.get_project_state(turn_events[0].turn.project_id) is not None


def test_stream_turn_validates_eagerly(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch)
    runtime = _build_runtime(tmp_path)
    with pytest.raises(ValueError, match="must not be blank"):
        runtime.stream_turn("  ")
    with pytest.raises(KeyError, match="Unknown project_id"):
        runtime.stream_turn("resume", project_id="missing")


def test_profile_extraction_is_off_by_default(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch)
    runtime = _build_runtime(tmp_path)
    assert runtime.profile_extractor is None


def test_profile_extraction_runs_post_turn_when_wired(tmp_path: Path, monkeypatch) -> None:
    _install_fake_agent(monkeypatch)
    extractor = _StubProfileExtractor(
        ProfileAnalysis(profile_update=UserProfileUpdate(role="Backend engineer"))
    )
    runtime = _build_runtime(tmp_path, profile_extractor=extractor)

    runtime.run_turn("I'm a backend engineer working through an idea.")

    assert extractor.calls
    assert runtime.get_user_profile().role == "Backend engineer"


def test_enabling_profile_extraction_auto_constructs_an_extractor(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        prompt_dir=Path("prompts"),
        enable_profile_extraction=True,
        openrouter_api_key=SecretStr("test-key"),
    )
    runtime = ThinkingRuntime(
        settings=settings,
        agent_model=object(),
        gate_model=object(),
        frame_analyst=object(),
        explorer=object(),
        synthesizer=object(),
        planner=object(),
        evidence_analyst=object(),
        store=None,
        context_retriever=None,
    )
    assert isinstance(runtime.profile_extractor, ProfileExtractor)


def test_create_runtime_honors_explicit_database_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mythinking.runtime.create_chat_model", lambda settings: object())
    monkeypatch.setattr("mythinking.runtime.create_embeddings_model", lambda settings: object())

    class _NullStoreCM:
        def __enter__(self):
            return object()

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr("mythinking.runtime.open_document_store", lambda *a, **k: _NullStoreCM())
    settings = Settings(
        _env_file=None,
        openrouter_api_key=SecretStr("test-key"),
        data_dir=tmp_path / "default-data",
        prompt_dir=Path("prompts"),
    )
    state_database_path = tmp_path / "custom" / "state.db"
    checkpoint_database_path = tmp_path / "custom" / "checkpoints.db"

    runtime = create_runtime(
        settings=settings,
        state_database_path=state_database_path,
        checkpoint_database_path=checkpoint_database_path,
    )

    assert runtime.repository.database_path == state_database_path
    assert runtime.checkpoint_database_path == checkpoint_database_path


# Frame analyses are exercised through tool tests, not here; kept import-alive.
_ = FrameAnalysis


# --------------------------------------------------------------- direct edits


def _seed(runtime: ThinkingRuntime, **fields) -> ProjectState:
    state = ProjectState(
        north_star=NorthStar(title="Note app", problem_statement="Notes get lost"),
        **fields,
    )
    runtime.repository.save(state)
    return state


def test_edit_north_star_updates_the_title(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime)

    updated = runtime.edit_north_star(seeded.project_id, title="  Personal KB  ")

    assert updated.north_star.title == "Personal KB"
    assert runtime.get_project_state(seeded.project_id).north_star.title == "Personal KB"


def test_edit_north_star_rejects_blank_title(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime)

    with pytest.raises(ValueError):
        runtime.edit_north_star(seeded.project_id, title="   ")


def test_edit_north_star_unknown_project_raises_keyerror(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)

    with pytest.raises(KeyError):
        runtime.edit_north_star("nope", title="x")


def test_add_edit_and_delete_decision(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime)

    added = runtime.add_decision(seeded.project_id, question="Sync?", choice="Single-device for v1")
    assert [d.choice for d in added.decisions] == ["Single-device for v1"]
    decision_id = added.decisions[0].id

    edited = runtime.edit_decision(
        seeded.project_id, decision_id, rationale="less complexity", reversible=False
    )
    assert edited.decisions[0].rationale == "less complexity"
    assert edited.decisions[0].reversible is False

    cleared = runtime.delete_decision(seeded.project_id, decision_id)
    assert cleared.decisions == []


def test_edit_decision_unknown_id_raises_keyerror(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime)

    with pytest.raises(KeyError):
        runtime.edit_decision(seeded.project_id, "missing", choice="x")


def test_approve_proposal_commits_and_marks_agent_plan_stale(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(
        runtime,
        proposal=DirectionProposal(statement="Ship the app", rationale="fewest unknowns"),
        next_actions=[
            NextAction(description="agent step", origin="agent"),
            NextAction(description="my step", origin="user"),
        ],
    )

    committed = runtime.approve_proposal(seeded.project_id)

    assert committed.north_star.current_hypothesis == "Ship the app"
    assert committed.proposal is None
    assert committed.decisions[0].question == "Committed project direction"
    by_desc = {a.description: a for a in committed.next_actions}
    assert by_desc["agent step"].stale is True
    assert by_desc["my step"].stale is False


def test_approve_proposal_without_a_proposal_raises_valueerror(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime)

    with pytest.raises(ValueError):
        runtime.approve_proposal(seeded.project_id)


def test_dismiss_proposal_clears_it(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime, proposal=DirectionProposal(statement="maybe this"))

    cleared = runtime.dismiss_proposal(seeded.project_id)

    assert cleared.proposal is None


def test_add_next_action_is_tagged_user_and_survives_replanning(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime)

    updated = runtime.add_next_action(
        seeded.project_id, description="Call three note-app users", time_box_minutes=45
    )

    assert updated.next_actions[0].origin == "user"
    assert updated.next_actions[0].time_box_minutes == 45


def test_add_next_action_rejects_blank_description(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime)

    with pytest.raises(ValueError):
        runtime.add_next_action(seeded.project_id, description="  ")


def test_edit_and_delete_next_action(tmp_path: Path) -> None:
    runtime = _build_runtime(tmp_path)
    seeded = _seed(runtime, next_actions=[NextAction(description="rough draft")])
    action_id = seeded.next_actions[0].id

    edited = runtime.edit_next_action(
        seeded.project_id, action_id, description="Prototype FTS5 search", completed=True
    )
    assert edited.next_actions[0].description == "Prototype FTS5 search"
    assert edited.next_actions[0].completed is True

    cleared = runtime.delete_next_action(seeded.project_id, action_id)
    assert cleared.next_actions == []
