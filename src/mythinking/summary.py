"""Deterministic, offline rendering of a project's session summary.

Used for the `mythinking show` command and other resume-flow surfaces so a
user can see where a session left off without a model call.
"""

from mythinking.state import BranchStatus, ProjectState, ResearchTaskStatus


def format_project_summary(project_state: ProjectState) -> str:
    north_star = project_state.north_star
    lines = [
        f"Project: {project_state.project_id}",
        f"Title: {north_star.title}",
        f"Mode: {project_state.current_mode.value}",
        f"Last updated: {project_state.updated_at.isoformat()}",
        "",
    ]

    frame_lines = []
    if north_star.problem_statement:
        frame_lines.append(f"  Problem: {north_star.problem_statement}")
    if north_star.desired_outcome:
        frame_lines.append(f"  Outcome: {north_star.desired_outcome}")
    if north_star.current_hypothesis:
        frame_lines.append(f"  Hypothesis: {north_star.current_hypothesis}")
    if frame_lines:
        lines.append("North star:")
        lines.extend(frame_lines)
    else:
        lines.append("North star: not yet framed")
    lines.append("")

    active_branch_id = project_state.active_branch_id
    active_branch = next(
        (branch for branch in project_state.branches if branch.id == active_branch_id),
        None,
    )
    lines.append(f"Active branch: {active_branch.name if active_branch else 'none (main thread)'}")
    parked = [branch for branch in project_state.branches if branch.status is BranchStatus.PARKED]
    if parked:
        lines.append(f"Parked branches: {', '.join(branch.name for branch in parked)}")

    lines.append(f"Open questions: {len(project_state.open_questions)}")
    open_research_tasks = [
        task for task in project_state.research_tasks if task.status is ResearchTaskStatus.OPEN
    ]
    lines.append(f"Open research tasks: {len(open_research_tasks)}")

    if project_state.decisions:
        latest_decision = project_state.decisions[-1]
        lines.append(f"Latest decision: {latest_decision.choice} (for: {latest_decision.question})")
    else:
        lines.append("Latest decision: none yet")

    open_next_actions = [action for action in project_state.next_actions if not action.completed]
    if open_next_actions:
        lines.append(f"Next action: {open_next_actions[0].description}")
    elif north_star.next_action:
        lines.append(f"Next action: {north_star.next_action}")
    else:
        lines.append("Next action: not captured yet")

    return "\n".join(lines)
