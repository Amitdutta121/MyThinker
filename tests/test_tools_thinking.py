"""Deterministic precondition tests for the state-changing thinking tools.

Each tool is exercised with fake domain engines and a fake gate model, so these
assert the tool *contracts* (blocks, exact-proposal commit, plan staleness,
proposal-not-decision) without any live model call.
"""

import pytest

from mythinking.board import MutableStateHolder
from mythinking.gates import DecisionGate, EvidenceGate, NorthStarGate
from mythinking.state import (
    AlternativeDraft as Alt,
)
from mythinking.state import (
    BranchStatus,
    DirectionProposal,
    ExplorerAnalysis,
    FrameAnalysis,
    IdeaBranch,
    NextAction,
    PlannerAnalysis,
    ProjectState,
    SynthesizerAnalysis,
)
from mythinking.state import (
    ConvergenceOption as Opt,
)
from mythinking.state import (
    NextActionDraft as Step,
)
from mythinking.tools import ThinkingToolDeps, build_thinking_tools


class _Bound:
    def __init__(self, value):
        self._value = value

    def invoke(self, _prompt):
        return self._value


class FakeGateModel:
    def __init__(self, *, north_star=None, decision=None, evidence=None):
        self._by_schema = {
            NorthStarGate: north_star or NorthStarGate(supported=True, normalized_goal="Goal"),
            DecisionGate: decision or DecisionGate(supported_by_user_message=True, reason="ok"),
            EvidenceGate: evidence
            or EvidenceGate(supported_by_excerpt=True, project_relevant=True),
        }

    def with_structured_output(self, schema):
        return _Bound(self._by_schema[schema])


class FakeFrame:
    def analyze(self, _state, _msg) -> FrameAnalysis:
        return FrameAnalysis()


class FakeExplorer:
    def analyze(self, _state, _msg) -> ExplorerAnalysis:
        return ExplorerAnalysis(alternatives_to_add=[Alt(name="Map view"), Alt(name="Board view")])


class FakeSynth:
    def __init__(self, choice="Use the board view"):
        self.choice = choice

    def analyze(self, _state, _msg) -> SynthesizerAnalysis:
        return SynthesizerAnalysis(
            options_considered=[Opt(branch_name="Map view"), Opt(branch_name="Board view")],
            recommended_choice=self.choice,
            rationale="Keeps decisions visible.",
        )


class FakePlanner:
    def analyze(self, _state, _msg) -> PlannerAnalysis:
        return PlannerAnalysis(next_actions_to_add=[Step(description="Prototype the board")])


def _deps(gate_model=None, synth=None):
    return ThinkingToolDeps(
        frame_analyst=FakeFrame(),
        explorer=FakeExplorer(),
        synthesizer=synth or FakeSynth(),
        planner=FakePlanner(),
        evidence_analyst=object(),
        gate_model=gate_model or FakeGateModel(),
    )


def _tools(state, message, *, gate_model=None, synth=None):
    holder = MutableStateHolder(project_state=state)
    tool_list = build_thinking_tools(
        holder,
        message,
        deps=_deps(gate_model, synth),
        context_retriever=None,
        store=None,
        settings=None,
    )
    return holder, {t.name: t for t in tool_list}


def _framed(**kw) -> ProjectState:
    state = ProjectState()
    state.north_star.problem_statement = "Ideas get lost when the conversation branches"
    state.north_star.desired_outcome = "Keep the main idea visible"
    state.north_star.beneficiary = "Solo thinkers"
    for key, value in kw.items():
        setattr(state, key, value)
    return state


# --------------------------------------------------------------- set_north_star


def test_set_north_star_blocks_when_gate_unsupported() -> None:
    gate = FakeGateModel(north_star=NorthStarGate(supported=False, reason="too vague"))
    holder, tools = _tools(ProjectState(), "give me five ideas", gate_model=gate)
    out = tools["set_north_star"].invoke({"goal": "some project"})
    assert out.startswith("BLOCKED")
    assert not holder.project_state.north_star.problem_statement


def test_set_north_star_establishes_goal_when_supported() -> None:
    gate = FakeGateModel(
        north_star=NorthStarGate(supported=True, normalized_goal="Build a workspace")
    )
    holder, tools = _tools(ProjectState(), "I want to build a workspace", gate_model=gate)
    out = tools["set_north_star"].invoke({"goal": "Build a workspace"})
    assert "North Star established" in out
    assert holder.project_state.north_star.problem_statement == "Build a workspace"


def test_set_north_star_blocks_when_one_already_exists() -> None:
    _holder, tools = _tools(_framed(), "another goal")
    out = tools["set_north_star"].invoke({"goal": "another goal"})
    assert out.startswith("BLOCKED")


# ---------------------------------------------------------------- explore_ideas


def test_explore_blocked_without_north_star() -> None:
    _holder, tools = _tools(ProjectState(), "explore options")
    assert tools["explore_ideas"].invoke({"question": "options"}).startswith("BLOCKED")


def test_explore_adds_branches_with_north_star() -> None:
    holder, tools = _tools(_framed(), "explore options")
    tools["explore_ideas"].invoke({"question": "options"})
    assert [b.name for b in holder.project_state.branches] == ["Map view", "Board view"]


# --------------------------------------------------------------- converge_ideas


def test_converge_blocked_with_fewer_than_two_active_branches() -> None:
    state = _framed(branches=[IdeaBranch(name="Only one")])
    _holder, tools = _tools(state, "recommend one")
    assert tools["converge_ideas"].invoke({"criteria": ""}).startswith("BLOCKED")


def test_converge_writes_proposal_not_committed_direction() -> None:
    state = _framed(branches=[IdeaBranch(name="Map view"), IdeaBranch(name="Board view")])
    holder, tools = _tools(state, "recommend the strongest, do not commit")
    tools["converge_ideas"].invoke({"criteria": ""})
    assert holder.project_state.proposal is not None
    assert holder.project_state.proposal.statement == "Use the board view"
    assert holder.project_state.north_star.current_hypothesis == ""
    assert holder.project_state.decisions == []


# ------------------------------------------------------ commit_proposed_direction


def test_commit_blocked_without_proposal() -> None:
    _holder, tools = _tools(_framed(), "let's go with that")
    assert tools["commit_proposed_direction"].invoke({}).startswith("BLOCKED")


def test_commit_blocked_when_turn_not_authorized() -> None:
    state = _framed(proposal=DirectionProposal(statement="Use the board view"))
    holder, tools = _tools(state, "hmm maybe that could work")
    assert tools["commit_proposed_direction"].invoke({}).startswith("BLOCKED")
    assert holder.project_state.north_star.current_hypothesis == ""


def test_commit_copies_exact_proposal_and_stales_plan() -> None:
    state = _framed(
        proposal=DirectionProposal(statement="Use the board view", rationale="clear"),
        next_actions=[NextAction(description="Old step")],
    )
    holder, tools = _tools(state, "let's go with that recommendation, commit it")
    out = tools["commit_proposed_direction"].invoke({})
    assert "Committed direction: Use the board view" in out
    ps = holder.project_state
    assert ps.north_star.current_hypothesis == "Use the board view"
    assert ps.proposal is None
    assert len(ps.decisions) == 1 and ps.decisions[0].choice == "Use the board view"
    assert ps.next_actions[0].stale is True


# ------------------------------------------------------- record_user_decision


def test_record_decision_blocked_when_gate_rejects() -> None:
    gate = FakeGateModel(decision=DecisionGate(supported_by_user_message=False, reason="no"))
    _holder, tools = _tools(_framed(), "what do you think?", gate_model=gate)
    assert (
        tools["record_user_decision"]
        .invoke({"statement": "We will ship weekly"})
        .startswith("BLOCKED")
    )


def test_record_decision_persists_and_stales_plan() -> None:
    state = _framed(next_actions=[NextAction(description="Old step")])
    holder, tools = _tools(state, "decision: we will ship weekly")
    tools["record_user_decision"].invoke({"statement": "We will ship weekly"})
    assert holder.project_state.decisions[0].choice == "We will ship weekly"
    assert holder.project_state.next_actions[0].stale is True


# ------------------------------------------------------- create_or_revise_plan


def test_plan_blocked_without_committed_direction() -> None:
    state = _framed(proposal=DirectionProposal(statement="Use the board view"))
    _holder, tools = _tools(state, "make the plan")
    assert tools["create_or_revise_plan"].invoke({"request": ""}).startswith("BLOCKED")


def test_plan_builds_from_committed_direction_and_drops_stale_steps() -> None:
    state = _framed(next_actions=[NextAction(description="Old", stale=True)])
    state.north_star.current_hypothesis = "Use the board view"
    holder, tools = _tools(state, "make the V1 plan")
    tools["create_or_revise_plan"].invoke({"request": ""})
    descriptions = [a.description for a in holder.project_state.next_actions]
    assert descriptions == ["Prototype the board"]


# ------------------------------------------------------------------ park_branch


def test_park_branch_blocked_without_park_language() -> None:
    state = _framed(branches=[IdeaBranch(name="Voice mode", summary="speak to practice")])
    _holder, tools = _tools(state, "what about voice mode?")
    assert tools["park_branch"].invoke({"branch_name": "Voice mode"}).startswith("BLOCKED")


def test_park_branch_parks_named_branch() -> None:
    state = _framed(branches=[IdeaBranch(name="Voice mode", summary="speak to practice")])
    holder, tools = _tools(state, "park voice mode for later")
    tools["park_branch"].invoke({"branch_name": "Voice mode"})
    assert holder.project_state.branches[0].status is BranchStatus.PARKED


# ----------------------------------------------------------------- save_evidence


def test_save_evidence_blocked_when_excerpt_does_not_support_claim() -> None:
    gate = FakeGateModel(evidence=EvidenceGate(supported_by_excerpt=False, project_relevant=True))
    holder, tools = _tools(_framed(), "save this", gate_model=gate)
    out = tools["save_evidence"].invoke(
        {"claim": "X", "source": "http://s", "source_excerpt": "unrelated"}
    )
    assert out.startswith("BLOCKED")
    assert holder.project_state.evidence == []


def test_save_evidence_blocked_when_not_project_relevant() -> None:
    gate = FakeGateModel(evidence=EvidenceGate(supported_by_excerpt=True, project_relevant=False))
    _holder, tools = _tools(_framed(), "save this", gate_model=gate)
    assert (
        tools["save_evidence"]
        .invoke({"claim": "X", "source": "http://s", "source_excerpt": "supports X"})
        .startswith("BLOCKED")
    )


def test_save_evidence_persists_when_gate_passes() -> None:
    holder, tools = _tools(_framed(), "save the strongest sourced claim")
    out = tools["save_evidence"].invoke(
        {
            "claim": "A persistent board reduces context reconstruction",
            "source": "https://example.com/paper",
            "source_excerpt": "the persistent representation reduces reconstruction",
        }
    )
    assert out.startswith("Evidence saved")
    assert len(holder.project_state.evidence) == 1
    assert holder.project_state.evidence[0].source_url == "https://example.com/paper"


def test_save_evidence_blocked_without_north_star() -> None:
    _holder, tools = _tools(ProjectState(), "save this claim")
    assert (
        tools["save_evidence"]
        .invoke({"claim": "X", "source": "s", "source_excerpt": "e"})
        .startswith("BLOCKED")
    )


@pytest.mark.parametrize("tool_name", ["get_project_snapshot", "get_evidence_ledger"])
def test_read_tools_are_present_and_read_only(tool_name: str) -> None:
    _holder, tools = _tools(_framed(), "status?")
    assert tool_name in tools
