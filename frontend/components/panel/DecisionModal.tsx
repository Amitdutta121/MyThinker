"use client";

import { useState } from "react";
import { deleteDecision, patchDecision } from "@/lib/api-client";
import type { Decision, ProjectState } from "@/lib/types";
import ConfirmDialog from "./ConfirmDialog";
import Modal from "./Modal";

const FIELD_CLASS =
  "mt-1 w-full rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]";
const BTN =
  "rounded border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text)]";

export default function DecisionModal({
  projectId,
  decision,
  onStateChange,
  onClose,
}: {
  projectId: string;
  decision: Decision;
  onStateChange: (next: ProjectState) => void;
  onClose: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    question: decision.question,
    choice: decision.choice,
    rationale: decision.rationale ?? "",
    reversible: decision.reversible,
  });

  const saveEdit = async () => {
    setBusy(true);
    try {
      onStateChange(
        await patchDecision(projectId, decision.id as string, {
          question: form.question,
          choice: form.choice,
          rationale: form.rationale,
          reversible: form.reversible,
        }),
      );
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  const doDelete = async () => {
    setBusy(true);
    try {
      onStateChange(await deleteDecision(projectId, decision.id as string));
      onClose();
    } finally {
      setBusy(false);
    }
  };

  const footer = editing ? (
    <>
      <button type="button" className={BTN} onClick={() => setEditing(false)} disabled={busy}>
        Cancel
      </button>
      <button
        type="button"
        onClick={saveEdit}
        disabled={busy || !form.choice.trim()}
        className="rounded bg-[var(--mode-accent)] px-3 py-1.5 text-xs font-medium text-black disabled:opacity-50"
      >
        Save
      </button>
    </>
  ) : (
    <>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        disabled={busy}
        className="rounded border border-[var(--border)] px-3 py-1.5 text-xs text-red-300 hover:text-red-200"
      >
        Delete
      </button>
      <button type="button" className={BTN} onClick={() => setEditing(true)} disabled={busy}>
        Edit
      </button>
    </>
  );

  return (
    <Modal title="Decision" onClose={onClose} footer={footer}>
      {editing ? (
        <div className="space-y-3">
          <label className="block text-xs text-[var(--text-muted)]">
            Question
            <input
              value={form.question}
              onChange={(e) => setForm({ ...form, question: e.target.value })}
              className={FIELD_CLASS}
            />
          </label>
          <label className="block text-xs text-[var(--text-muted)]">
            Choice
            <input
              value={form.choice}
              onChange={(e) => setForm({ ...form, choice: e.target.value })}
              className={FIELD_CLASS}
            />
          </label>
          <label className="block text-xs text-[var(--text-muted)]">
            Rationale
            <textarea
              value={form.rationale}
              onChange={(e) => setForm({ ...form, rationale: e.target.value })}
              rows={3}
              className={FIELD_CLASS}
            />
          </label>
          <label className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <input
              type="checkbox"
              checked={form.reversible}
              onChange={(e) => setForm({ ...form, reversible: e.target.checked })}
            />
            Reversible
          </label>
        </div>
      ) : (
        <div className="space-y-2">
          {decision.question ? (
            <p className="text-xs font-medium text-[var(--text-muted)]">
              {decision.question}
            </p>
          ) : null}
          <p className="text-sm font-medium">{decision.choice}</p>
          {decision.rationale ? (
            <p className="text-sm text-[var(--text-muted)]">{decision.rationale}</p>
          ) : null}
          {(decision.alternatives ?? []).length > 0 ? (
            <div>
              <p className="text-xs font-medium text-[var(--text-muted)]">
                Alternatives considered
              </p>
              <ul className="mt-0.5 list-disc pl-4 text-sm text-[var(--text-muted)]">
                {(decision.alternatives ?? []).map((alt, index) => (
                  <li key={index}>{alt}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <span
            className={`inline-block rounded-full px-2 py-0.5 text-xs ${
              decision.reversible
                ? "bg-[var(--mode-accent-soft)] text-[var(--mode-accent)]"
                : "bg-red-500/10 text-red-300"
            }`}
          >
            {decision.reversible ? "reversible" : "irreversible"}
          </span>
        </div>
      )}

      {confirming ? (
        <ConfirmDialog
          message="Delete this decision? This can't be undone."
          onConfirm={doDelete}
          onCancel={() => setConfirming(false)}
        />
      ) : null}
    </Modal>
  );
}
