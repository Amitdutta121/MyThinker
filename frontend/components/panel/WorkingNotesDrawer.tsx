"use client";

import { useState } from "react";
import type { ProjectState } from "@/lib/types";
import Icon from "../Icon";
import NoteModal, { type Note } from "./NoteModal";

type Row = {
  key: string | undefined;
  text: string;
  tag: string;
  warn?: boolean;
  note: Note;
};

function Group({
  label,
  rows,
  onOpen,
}: {
  label: string;
  rows: Row[];
  onOpen: (note: Note) => void;
}) {
  if (rows.length === 0) return null;
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-[var(--text-muted)]">{label}</p>
      <ul className="space-y-1">
        {rows.map((row) => (
          <li key={row.key}>
            <button
              type="button"
              onClick={() => onOpen(row.note)}
              className="flex w-full items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-raised)] px-2 py-1.5 text-left text-xs hover:border-[var(--mode-accent)]"
            >
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase ${
                  row.warn
                    ? "bg-amber-500/15 text-amber-300"
                    : "bg-[var(--bg)] text-[var(--text-muted)]"
                }`}
              >
                {row.tag}
              </span>
              <span className="min-w-0 flex-1 truncate text-[var(--text)]">{row.text}</span>
              <Icon name="chevron-right" size={12} className="shrink-0 text-[var(--text-muted)]" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The escape hatch: everything the agent tracks but the user doesn't manage —
 * assumptions, evidence, options (branches), open research questions, loose
 * ends. Collapsed by default; each row opens a read-only `NoteModal`.
 */
export default function WorkingNotesDrawer({ state }: { state: ProjectState }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState<Note | null>(null);

  const assumptions = state.assumptions ?? [];
  const evidence = state.evidence ?? [];
  const branches = state.branches ?? [];
  const research = state.research_tasks ?? [];
  const looseEnds = [...(state.open_questions ?? []), ...(state.parked_ideas ?? [])];
  const total =
    assumptions.length +
    evidence.length +
    branches.length +
    research.length +
    looseEnds.length;

  if (total === 0) return null;

  return (
    <section className="overflow-hidden rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface)]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-2.5 text-sm text-[var(--text-muted)] hover:text-[var(--text)]"
      >
        <span>Agent&apos;s working notes</span>
        <span className="flex items-center gap-1.5 tabular-nums">
          {total}
          <Icon name={open ? "chevron-up" : "chevron-down"} size={12} />
        </span>
      </button>
      {open ? (
        <div className="space-y-4 border-t border-[var(--border)] px-4 py-3">
          <Group
            label="Assumptions"
            onOpen={setNote}
            rows={assumptions.map((a) => ({
              key: a.id,
              text: a.statement,
              tag: a.status,
              warn: a.status === "challenged" || a.status === "rejected",
              note: { kind: "assumption", data: a },
            }))}
          />
          <Group
            label="Evidence"
            onOpen={setNote}
            rows={evidence.map((e) => ({
              key: e.id,
              text: e.claim,
              tag: e.kind,
              note: { kind: "evidence", data: e },
            }))}
          />
          <Group
            label="Options"
            onOpen={setNote}
            rows={branches.map((b) => ({
              key: b.id,
              text: b.name,
              tag: b.status,
              note: { kind: "branch", data: b },
            }))}
          />
          <Group
            label="Questions being looked into"
            onOpen={setNote}
            rows={research.map((r) => ({
              key: r.id,
              text: r.question,
              tag: r.status,
              note: { kind: "research", data: r },
            }))}
          />
          {looseEnds.length > 0 ? (
            <div>
              <p className="mb-1 text-xs font-medium text-[var(--text-muted)]">
                Loose ends
              </p>
              <ul className="space-y-1">
                {looseEnds.map((item, index) => (
                  <li key={index} className="text-xs text-[var(--text-muted)]">
                    • {item}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
      {note ? <NoteModal note={note} onClose={() => setNote(null)} /> : null}
    </section>
  );
}
