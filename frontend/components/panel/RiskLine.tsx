"use client";

import type { ProjectState } from "@/lib/types";
import Icon from "../Icon";

/**
 * Zero or one amber line, shown only when something needs the user. Priority:
 * a stale plan step, then a shaky load-bearing assumption, then an unapproved
 * proposal. The "Fix" button hands an instruction to the composer.
 */
export default function RiskLine({
  state,
  onPrefillComposer,
}: {
  state: ProjectState;
  onPrefillComposer?: (text: string) => void;
}) {
  const staleStep = (state.next_actions ?? []).find((a) => a.stale && !a.completed);
  const shakyAssumption = (state.assumptions ?? []).find(
    (a) => a.status === "challenged" && a.importance >= 4,
  );

  let risk: { text: string; instruction: string } | null = null;
  if (staleStep) {
    risk = {
      text: "The plan may be out of date — the direction changed after it was written.",
      instruction: "Rework the plan for the current direction.",
    };
  } else if (shakyAssumption) {
    risk = {
      text: `You're leaning on a shaky assumption: “${shakyAssumption.statement}”.`,
      instruction: `Pressure-test the assumption that ${shakyAssumption.statement}`,
    };
  } else if (state.proposal) {
    risk = {
      text: "A proposed direction is waiting for your approval.",
      instruction: "",
    };
  }

  if (!risk) return null;

  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200"
    >
      <Icon name="alert" size={13} className="mt-0.5 shrink-0" />
      <span className="flex-1">{risk.text}</span>
      {risk.instruction && onPrefillComposer ? (
        <button
          type="button"
          onClick={() => onPrefillComposer(risk.instruction)}
          className="shrink-0 font-medium underline underline-offset-2 hover:text-amber-100"
        >
          Fix
        </button>
      ) : null}
    </div>
  );
}
