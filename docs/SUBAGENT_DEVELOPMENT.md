# Subagent-Driven Development

This repository is intended to be implemented by a lead Codex session that may
delegate tightly scoped work to subagents in later sessions.

## Operating model

- The lead Codex session acts as the implementation supervisor.
- Subagents do not invent architecture. They implement against fixed contracts.
- Parallel work is allowed only when interfaces are already defined.
- The lead session integrates, verifies, and resolves conflicts.

## Required order of work

1. Read [AGENTS.md](D:/MyThinking/AGENTS.md) and [IMPLEMENTATION_PLAN.md](D:/MyThinking/docs/IMPLEMENTATION_PLAN.md).
2. Select one milestone.
3. Freeze the interfaces for that milestone.
4. Split work into independent slices.
5. Delegate slices to subagents only if they can be integrated without
   ambiguity.
6. Re-run tests and reconcile the outputs in the lead session.

## Good subagent tasks

- write tests for an already-defined module,
- implement a specialist prompt loader for a defined schema,
- add persistence methods against an existing state model,
- add CLI parsing for an already-defined runtime function.

## Bad subagent tasks

- redesign the architecture,
- invent state fields without updating the contract,
- choose libraries,
- change prompt behavior without eval updates,
- touch overlapping files in incompatible ways.

## Subagent contract template

Each delegated task should specify:

- objective,
- exact files in scope,
- non-goals,
- acceptance criteria,
- tests to add or update,
- integration assumptions.

## Review contract

The lead session should reject subagent work if:

- interfaces drifted,
- tests are missing,
- prompts changed without evidence or eval updates,
- a dependency was added without necessity,
- implementation duplicated a library abstraction already in the stack.

## File ownership by concern

- `src/mythinking/state.py`: domain schema authority
- `src/mythinking/persistence.py`: local persistence authority
- `src/mythinking/llm.py`: model construction authority
- `prompts/*.yaml`: prompt authority
- `evals/cases.jsonl`: behavior fixture authority
- `tests/`: verification authority

## Multi-session handoff expectation

Every substantial session should leave behind:

- updated code,
- passing tests or a clear failing test target,
- doc updates if interfaces changed,
- a concise note of what the next session should build.
