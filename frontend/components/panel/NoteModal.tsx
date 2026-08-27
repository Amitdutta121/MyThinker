"use client";

import type { Assumption, EvidenceItem, IdeaBranch, ResearchTask } from "@/lib/types";
import Modal from "./Modal";

export type Note =
  | { kind: "assumption"; data: Assumption }
  | { kind: "evidence"; data: EvidenceItem }
  | { kind: "branch"; data: IdeaBranch }
  | { kind: "research"; data: ResearchTask };

const TITLE: Record<Note["kind"], string> = {
  assumption: "Assumption",
  evidence: "Evidence",
  branch: "Option",
  research: "Open question",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  if (!children) return null;
  return (
    <div>
      <p className="text-xs font-medium text-[var(--text-muted)]">{label}</p>
      <p className="mt-0.5 text-sm">{children}</p>
    </div>
  );
}

/**
 * Read-only detail for a working-notes row. The agent maintains this state; the
 * panel only shows it — to change it, the user talks to the agent.
 */
export default function NoteModal({ note, onClose }: { note: Note; onClose: () => void }) {
  return (
    <Modal title={TITLE[note.kind]} onClose={onClose}>
      <div className="space-y-3">
        {note.kind === "assumption" ? (
          <>
            <p className="text-sm font-medium">{note.data.statement}</p>
            <Field label="Status">
              <span className="capitalize">{note.data.status}</span>
            </Field>
            <Field label="Importance">
              {"●".repeat(note.data.importance)}
              <span className="opacity-30">{"●".repeat(5 - note.data.importance)}</span>
            </Field>
            <Field label="Falsified if">{note.data.falsifying_evidence}</Field>
          </>
        ) : null}

        {note.kind === "evidence" ? (
          <>
            <p className="text-sm font-medium">{note.data.claim}</p>
            <Field label="Kind">
              <span className="capitalize">{note.data.kind}</span>
            </Field>
            <Field label="Source">
              {note.data.source_url ? (
                <a
                  href={note.data.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[var(--mode-accent)] hover:underline"
                >
                  {note.data.source_title || note.data.source_url}
                </a>
              ) : (
                note.data.source_title
              )}
            </Field>
            <Field label="Notes">{note.data.notes}</Field>
          </>
        ) : null}

        {note.kind === "branch" ? (
          <>
            <p className="text-sm font-medium">{note.data.name}</p>
            <Field label="Status">
              <span className="capitalize">{note.data.status}</span>
            </Field>
            <Field label="Summary">{note.data.summary}</Field>
            <Field label="Relation to the goal">{note.data.relationship_to_goal}</Field>
            <Field label="Revisit when">{note.data.revisit_trigger}</Field>
          </>
        ) : null}

        {note.kind === "research" ? (
          <>
            <p className="text-sm font-medium">{note.data.question}</p>
            <Field label="Status">
              <span className="capitalize">{note.data.status}</span>
            </Field>
            <Field label="Notes">{note.data.notes}</Field>
            <Field label="Linked evidence">
              {note.data.linked_evidence_ids?.length
                ? `${note.data.linked_evidence_ids.length} item(s)`
                : ""}
            </Field>
          </>
        ) : null}

        <p className="border-t border-[var(--border)] pt-3 text-xs text-[var(--text-muted)]">
          The agent maintains this. To change it, raise it in the conversation.
        </p>
      </div>
    </Modal>
  );
}
