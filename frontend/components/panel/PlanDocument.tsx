"use client";

import { useState } from "react";
import { addNextAction } from "@/lib/api-client";
import type { ProjectState } from "@/lib/types";
import PlanEditOverlay from "./PlanEditOverlay";

/** First sentence of a step, capped — used as a bold lead above the detail. */
function leadOf(description: string): string {
  const firstSentence = description.split(/(?<=[.!?])\s+/)[0] ?? description;
  return firstSentence.length > 64
    ? `${firstSentence.slice(0, 61).trimEnd()}…`
    : firstSentence;
}

/**
 * The plan as a document, not a checklist. Composed from `next_actions` plus the
 * committed/proposed direction. Steps the user added (`origin === "user"`) are
 * marked and survive re-planning; agent steps that went stale are flagged.
 */
export default function PlanDocument({
  projectId,
  state,
  onStateChange,
}: {
  projectId: string;
  state: ProjectState;
  onStateChange: (next: ProjectState) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);

  const actions = state.next_actions ?? [];
  const open = actions.filter((a) => !a.completed);
  const done = actions.filter((a) => a.completed);
  const committed = state.north_star?.current_hypothesis?.trim();
  const proposal = state.proposal;

  const submitStep = async () => {
    const description = draft.trim();
    if (!description) {
      setAdding(false);
      return;
    }
    setBusy(true);
    try {
      onStateChange(await addNextAction(projectId, { description }));
      setDraft("");
      setAdding(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-[var(--border)] border-l-[3px] border-l-[var(--mode-accent)] bg-[var(--surface)] py-4 pl-5 pr-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Plan</h2>
        {actions.length > 0 ? (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-muted)] hover:text-[var(--text)]"
          >
            Edit plan
          </button>
        ) : null}
      </div>

      {committed ? (
        <p className="mb-3 text-sm">
          <span className="text-[var(--text-muted)]">Working toward — </span>
          {committed}
        </p>
      ) : proposal ? (
        <p className="mb-3 text-sm">
          <span className="text-[var(--text-muted)]">Leaning toward — </span>
          {proposal.statement}{" "}
          <span className="text-[var(--text-muted)]">(not committed)</span>
        </p>
      ) : null}

      {open.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">
          No plan yet. Ask for a plan in the conversation, or add the first step below.
        </p>
      ) : (
        <div className="space-y-3">
          {open.map((action) => {
            const lead = leadOf(action.description);
            const meta = [
              `${action.time_box_minutes}m`,
              action.implementation_intention ? `when: ${action.implementation_intention}` : "",
              action.success_signal ? `done when: ${action.success_signal}` : "",
            ]
              .filter(Boolean)
              .join(" · ");
            return (
              <article key={action.id} className={action.stale ? "opacity-70" : ""}>
                <h3 className="text-sm font-medium">
                  {lead}
                  {action.origin === "user" ? (
                    <span className="ml-1.5 text-xs font-normal text-[var(--text-muted)]">
                      · added by you
                    </span>
                  ) : null}
                </h3>
                {action.description !== lead ? (
                  <p className="mt-0.5 text-sm text-[var(--text)]">{action.description}</p>
                ) : null}
                {meta ? (
                  <p className="mt-0.5 text-xs text-[var(--text-muted)]">{meta}</p>
                ) : null}
                {action.stale ? (
                  <p className="mt-0.5 text-xs text-amber-300/80">
                    May be out of date — the direction changed after this was planned.
                  </p>
                ) : null}
              </article>
            );
          })}
        </div>
      )}

      {adding ? (
        <div className="mt-3">
          <textarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitStep();
              if (e.key === "Escape") {
                setAdding(false);
                setDraft("");
              }
            }}
            rows={2}
            disabled={busy}
            placeholder="Describe a step you want in the plan"
            aria-label="New plan step"
            className="w-full rounded border border-[var(--mode-accent)] bg-[var(--bg)] p-2 text-sm"
          />
          <div className="mt-1.5 flex gap-2">
            <button
              type="button"
              onClick={submitStep}
              disabled={busy}
              className="rounded bg-[var(--mode-accent)] px-2.5 py-1 text-xs font-medium text-black disabled:opacity-50"
            >
              Add step
            </button>
            <button
              type="button"
              onClick={() => {
                setAdding(false);
                setDraft("");
              }}
              className="rounded border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text-muted)]"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="mt-3 text-xs font-medium text-[var(--mode-accent)] hover:underline"
        >
          + Add a step
        </button>
      )}

      {done.length > 0 ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-[var(--text-muted)]">
            Done ({done.length})
          </summary>
          <ul className="mt-1.5 space-y-1">
            {done.map((action) => (
              <li key={action.id} className="text-xs text-[var(--text-muted)] line-through">
                {action.description}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {editing ? (
        <PlanEditOverlay
          projectId={projectId}
          actions={actions}
          onStateChange={onStateChange}
          onClose={() => setEditing(false)}
        />
      ) : null}
    </section>
  );
}
