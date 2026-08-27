"use client";

import { useState } from "react";
import { addNextAction, deleteNextAction, patchNextAction } from "@/lib/api-client";
import type { NextAction, ProjectState } from "@/lib/types";
import Icon from "../Icon";
import Modal from "./Modal";

function StepRow({
  action,
  busy,
  onSave,
  onRemove,
}: {
  action: NextAction;
  busy: boolean;
  onSave: (description: string) => void;
  onRemove: () => void;
}) {
  const [text, setText] = useState(action.description);
  return (
    <div className="flex gap-2">
      <textarea
        value={text}
        disabled={busy}
        rows={2}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => {
          if (text.trim() && text.trim() !== action.description) onSave(text.trim());
        }}
        className="flex-1 rounded border border-[var(--border)] bg-[var(--bg)] p-2 text-sm text-[var(--text)]"
      />
      <button
        type="button"
        onClick={onRemove}
        disabled={busy}
        aria-label="Remove step"
        className="shrink-0 rounded border border-[var(--border)] px-2 text-red-300 hover:text-red-200"
      >
        <Icon name="close" size={13} />
      </button>
    </div>
  );
}

/**
 * Wide overlay for editing the plan — the one place the narrow side column is
 * genuinely too tight. Each change routes straight to a next-actions endpoint
 * and lifts the returned state.
 */
export default function PlanEditOverlay({
  projectId,
  actions,
  onStateChange,
  onClose,
}: {
  projectId: string;
  actions: NextAction[];
  onStateChange: (next: ProjectState) => void;
  onClose: () => void;
}) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [newStep, setNewStep] = useState("");

  const save = async (id: string, description: string) => {
    setBusyId(id);
    try {
      onStateChange(await patchNextAction(projectId, id, { description }));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (id: string) => {
    setBusyId(id);
    try {
      onStateChange(await deleteNextAction(projectId, id));
    } finally {
      setBusyId(null);
    }
  };

  const add = async () => {
    const description = newStep.trim();
    if (!description) return;
    setBusyId("new");
    try {
      onStateChange(await addNextAction(projectId, { description }));
      setNewStep("");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Modal title="Edit plan" onClose={onClose} wide>
      <div className="space-y-3">
        {actions.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No steps yet.</p>
        ) : (
          actions.map((action) => (
            <StepRow
              key={action.id}
              action={action}
              busy={busyId === action.id}
              onSave={(description) => save(action.id as string, description)}
              onRemove={() => remove(action.id as string)}
            />
          ))
        )}
        <div className="border-t border-[var(--border)] pt-3">
          <textarea
            value={newStep}
            onChange={(e) => setNewStep(e.target.value)}
            rows={2}
            placeholder="Add a step"
            aria-label="New plan step"
            className="w-full rounded border border-[var(--border)] bg-[var(--bg)] p-2 text-sm text-[var(--text)]"
          />
          <button
            type="button"
            onClick={add}
            disabled={busyId === "new" || !newStep.trim()}
            className="mt-1.5 rounded bg-[var(--mode-accent)] px-2.5 py-1 text-xs font-medium text-black disabled:opacity-50"
          >
            Add step
          </button>
        </div>
      </div>
    </Modal>
  );
}
