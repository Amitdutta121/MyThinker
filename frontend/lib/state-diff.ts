import type { ProjectState } from "./types";

/**
 * A short, human list of what a turn changed on the board, shown as a transient
 * ribbon above the workspace rail. Deliberately lossy: it names the salient
 * mutations ("Decision recorded", "2 assumptions added"), not every field.
 */
export function summarizeStateChange(
  prev: ProjectState | null,
  next: ProjectState,
): string[] {
  if (!prev) return [];
  const out: string[] = [];

  const arr = <T>(v: T[] | undefined | null): T[] => v ?? [];
  const added = (a: unknown[], b: unknown[]) => Math.max(0, b.length - a.length);
  const plural = (n: number, one: string, many = `${one}s`) =>
    `${n} ${n === 1 ? one : many}`;
  const countBy = <T>(v: T[] | undefined | null, pred: (x: T) => boolean) =>
    arr(v).filter(pred).length;

  const ns = prev.north_star;
  const nn = next.north_star;
  if (
    (ns?.title ?? "") !== (nn?.title ?? "") ||
    (ns?.problem_statement ?? "") !== (nn?.problem_statement ?? "") ||
    (ns?.current_hypothesis ?? "") !== (nn?.current_hypothesis ?? "") ||
    (ns?.next_action ?? "") !== (nn?.next_action ?? "")
  ) {
    out.push("North star updated");
  }

  const branchesAdded = added(arr(prev.branches), arr(next.branches));
  if (branchesAdded) out.push(`${plural(branchesAdded, "branch", "branches")} added`);
  const newlyParked =
    countBy(next.branches, (b) => b.status === "parked") -
    countBy(prev.branches, (b) => b.status === "parked");
  if (newlyParked > 0) out.push(`${plural(newlyParked, "branch", "branches")} parked`);

  const assumptionsAdded = added(arr(prev.assumptions), arr(next.assumptions));
  if (assumptionsAdded) out.push(`${plural(assumptionsAdded, "assumption")} added`);

  const evidenceAdded = added(arr(prev.evidence), arr(next.evidence));
  if (evidenceAdded) out.push(`${plural(evidenceAdded, "evidence item")} captured`);

  const researchAdded = added(arr(prev.research_tasks), arr(next.research_tasks));
  if (researchAdded) out.push(`${plural(researchAdded, "research task")} opened`);
  const researchAnswered =
    countBy(next.research_tasks, (t) => t.status === "answered") -
    countBy(prev.research_tasks, (t) => t.status === "answered");
  if (researchAnswered > 0) out.push(`${plural(researchAnswered, "research task")} answered`);

  const decisionsAdded = added(arr(prev.decisions), arr(next.decisions));
  if (decisionsAdded) out.push(`${plural(decisionsAdded, "decision")} recorded`);

  const hadProposal = prev.proposal != null;
  const hasProposal = next.proposal != null;
  if (!hadProposal && hasProposal) out.push("New proposed direction");
  else if (hadProposal && !hasProposal) out.push("Proposal committed");
  else if (
    hadProposal &&
    hasProposal &&
    prev.proposal!.statement !== next.proposal!.statement
  ) {
    out.push("Proposed direction revised");
  }

  const actionsAdded = added(arr(prev.next_actions), arr(next.next_actions));
  if (actionsAdded) out.push(`${plural(actionsAdded, "next action")} planned`);
  const newlyStale =
    countBy(next.next_actions, (a) => a.stale) - countBy(prev.next_actions, (a) => a.stale);
  if (newlyStale > 0) out.push("Plan marked stale");

  const questionsAdded = added(arr(prev.open_questions), arr(next.open_questions));
  if (questionsAdded) out.push(`${plural(questionsAdded, "open question")} added`);

  return out;
}
