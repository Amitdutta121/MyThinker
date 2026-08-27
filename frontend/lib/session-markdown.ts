import type { ProjectState } from "./types";

/**
 * Render a project's board as a portable Markdown document — the thing a user
 * pastes into a doc, a ticket, or a notebook when they're done thinking. Only
 * sections with content are emitted.
 */
export function sessionToMarkdown(state: ProjectState): string {
  const out: string[] = [];
  const ns = state.north_star;

  out.push(`# ${ns?.title?.trim() || "Untitled session"}`);

  if (ns?.problem_statement?.trim()) {
    out.push("", `**Problem.** ${ns.problem_statement.trim()}`);
  }
  if (ns?.desired_outcome?.trim()) {
    out.push("", `**Desired outcome.** ${ns.desired_outcome.trim()}`);
  }
  if (ns?.current_hypothesis?.trim()) {
    out.push("", `**Current direction.** ${ns.current_hypothesis.trim()}`);
  }

  const bullets = (label: string, items?: string[]) => {
    const list = (items ?? []).map((s) => s.trim()).filter(Boolean);
    if (list.length === 0) return;
    out.push("", `## ${label}`, ...list.map((s) => `- ${s}`));
  };

  bullets("Constraints", ns?.constraints);
  bullets("Success criteria", ns?.success_criteria);
  bullets("Non-goals", ns?.non_goals);

  const proposal = state.proposal;
  if (proposal) {
    out.push("", "## Proposed direction (not committed)", proposal.statement.trim());
    if (proposal.rationale?.trim()) out.push("", `_Why:_ ${proposal.rationale.trim()}`);
    const alts = (proposal.alternatives_considered ?? []).map((s) => s.trim()).filter(Boolean);
    if (alts.length) out.push("", "_Alternatives considered:_", ...alts.map((s) => `- ${s}`));
  }

  const branches = state.branches ?? [];
  if (branches.length) {
    out.push("", "## Branches");
    for (const b of branches) {
      out.push(`- **${b.name}** (${b.status})${b.summary?.trim() ? ` — ${b.summary.trim()}` : ""}`);
    }
  }

  const assumptions = state.assumptions ?? [];
  if (assumptions.length) {
    out.push("", "## Assumptions");
    for (const a of [...assumptions].sort((x, y) => y.importance - x.importance)) {
      out.push(`- [${a.status}] ${a.statement.trim()}`);
    }
  }

  const evidence = state.evidence ?? [];
  if (evidence.length) {
    out.push("", "## Evidence");
    for (const e of evidence) {
      const src = e.source_url ? ` ([source](${e.source_url}))` : "";
      out.push(`- _${e.kind}_ — ${e.claim.trim()}${src}`);
    }
  }

  const research = (state.research_tasks ?? []).filter((t) => t.status === "open");
  if (research.length) {
    out.push("", "## Open research questions");
    for (const t of research) out.push(`- ${t.question.trim()}`);
  }

  const decisions = state.decisions ?? [];
  if (decisions.length) {
    out.push("", "## Decisions");
    for (const d of [...decisions].sort(
      (x, y) => new Date(x.decided_at ?? 0).getTime() - new Date(y.decided_at ?? 0).getTime(),
    )) {
      out.push(
        `- **${d.choice.trim()}** — ${d.question.trim()}${d.reversible ? "" : " _(irreversible)_"}`,
      );
      if (d.rationale?.trim()) out.push(`  - _Why:_ ${d.rationale.trim()}`);
    }
  }

  const actions = (state.next_actions ?? []).filter((a) => !a.completed && !a.stale);
  if (actions.length) {
    out.push("", "## Plan — next steps");
    actions.forEach((a, i) => {
      out.push(`${i + 1}. ${a.description.trim()} _(${a.time_box_minutes}m)_`);
      if (a.implementation_intention?.trim()) out.push(`   - When: ${a.implementation_intention.trim()}`);
      if (a.success_signal?.trim()) out.push(`   - Success: ${a.success_signal.trim()}`);
    });
  }

  const questions = (state.open_questions ?? []).map((s) => s.trim()).filter(Boolean);
  if (questions.length) {
    out.push("", "## Open questions", ...questions.map((s) => `- ${s}`));
  }

  return out.join("\n").trim() + "\n";
}
