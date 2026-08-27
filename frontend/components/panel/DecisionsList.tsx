"use client";

import { useState } from "react";
import { addDecision, approveProposal, dismissProposal } from "@/lib/api-client";
import type { ProjectState } from "@/lib/types";
import DecisionModal from "./DecisionModal";

export default function DecisionsList({
  projectId,
  state,
  onStateChange,
  onPrefillComposer,
}: {
  projectId: string;
  state: ProjectState;
  onStateChange: (next: ProjectState) => void;
  onPrefillComposer?: (text: string) => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");

  const decisions = [...(state.decisions ?? [])].sort(
    (a, b) => new Date(b.decided_at ?? 0).getTime() - new Date(a.decided_at ?? 0).getTime(),
  );
  const proposal = state.proposal;
  const openDecision = decisions.find((d) => d.id === openId) ?? null;

  const approve = async () => {
    setBusy(true);
    try {
      onStateChange(await approveProposal(projectId));
    } finally {
      setBusy(false);
    }
  };

  const dismiss = async () => {
    setBusy(true);
    try {
      onStateChange(await dismissProposal(projectId));
    } finally {
      setBusy(false);
    }
  };

  const addManual = async () => {
    const choice = draft.trim();
    if (!choice) {
      setAdding(false);
      return;
    }
    setBusy(true);
    try {
      onStateChange(await addDecision(projectId, { choice }));
      setDraft("");
      setAdding(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="mb-3 text-sm font-semibold">Decisions</h2>

      {proposal ? (
        <div className="mb-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3">
          <p className="text-xs font-semibold text-amber-300">Pending — your call</p>
          <p className="mt-1 text-sm font-medium">{proposal.statement}</p>
          {proposal.rationale ? (
            <p className="mt-0.5 text-xs text-[var(--text-muted)]">{proposal.rationale}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={approve}
              disabled={busy}
              className="rounded bg-[var(--mode-accent)] px-2.5 py-1 text-xs font-medium text-black disabled:opacity-50"
            >
              Approve
            </button>
            <button
              type="button"
              disabled={busy || !onPrefillComposer}
              onClick={() => onPrefillComposer?.("Revise the proposed direction: ")}
              className="rounded border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text-muted)] hover:text-[var(--text)]"
            >
              Edit
            </button>
            <button
              type="button"
              onClick={dismiss}
              disabled={busy}
              className="rounded border border-[var(--border)] px-2.5 py-1 text-xs text-red-300 hover:text-red-200"
            >
              Dismiss
            </button>
          </div>
        </div>
      ) : null}

      {decisions.length === 0 && !proposal ? (
        <p className="text-sm text-[var(--text-muted)]">
          No decisions yet. Approve a direction, or add one you&apos;ve already made.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {decisions.map((decision) => (
            <li key={decision.id}>
              <button
                type="button"
                onClick={() => setOpenId(decision.id ?? null)}
                className="flex w-full items-center justify-between gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 text-left text-sm hover:border-[var(--mode-accent)]"
              >
                <span className="min-w-0 flex-1 truncate">{decision.choice}</span>
                <span
                  className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] uppercase ${
                    decision.reversible
                      ? "bg-[var(--mode-accent-soft)] text-[var(--mode-accent)]"
                      : "bg-red-500/10 text-red-300"
                  }`}
                >
                  {decision.reversible ? "reversible" : "firm"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {adding ? (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={addManual}
          onKeyDown={(e) => {
            if (e.key === "Enter") addManual();
            if (e.key === "Escape") {
              setAdding(false);
              setDraft("");
            }
          }}
          placeholder="What did you decide?"
          aria-label="New decision"
          className="mt-3 w-full rounded border border-[var(--mode-accent)] bg-[var(--bg)] px-2 py-1 text-sm"
        />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="mt-3 text-xs font-medium text-[var(--mode-accent)] hover:underline"
        >
          + Add a decision
        </button>
      )}

      {openDecision ? (
        <DecisionModal
          projectId={projectId}
          decision={openDecision}
          onStateChange={onStateChange}
          onClose={() => setOpenId(null)}
        />
      ) : null}
    </section>
  );
}
