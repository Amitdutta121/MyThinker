"use client";

import { useState } from "react";
import type { ProjectSummary } from "@/lib/types";
import { modeStyle } from "@/lib/modes";

function relativeTime(iso: string): string {
  const deltaMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(deltaMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export default function SessionSelector({
  projects,
  currentProjectId,
  onSelect,
  onNewSession,
}: {
  projects: ProjectSummary[];
  currentProjectId: string | null;
  onSelect: (projectId: string) => void;
  onNewSession: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text)]"
      >
        Sessions ({projects.length})
      </button>

      {open ? (
        <div className="absolute right-0 z-10 mt-2 w-80 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-2 shadow-xl">
          <button
            type="button"
            onClick={() => {
              onNewSession();
              setOpen(false);
            }}
            className="mb-1 w-full rounded-md px-2 py-1.5 text-left text-sm font-medium text-[var(--mode-accent)] hover:bg-[var(--surface)]"
          >
            + New session
          </button>

          {projects.length === 0 ? (
            <p className="px-2 py-2 text-xs text-[var(--text-muted)]">No sessions yet.</p>
          ) : (
            <ul className="max-h-80 overflow-y-auto">
              {projects.map((project) => {
                const style = modeStyle(project.current_mode);
                const active = project.project_id === currentProjectId;
                return (
                  <li key={project.project_id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(project.project_id);
                        setOpen(false);
                      }}
                      className={`flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-[var(--surface)] ${
                        active ? "bg-[var(--surface)]" : ""
                      }`}
                    >
                      <span className="truncate">{project.title}</span>
                      <span className="flex shrink-0 items-center gap-2 text-xs text-[var(--text-muted)]">
                        <span style={{ color: style.accent }}>{style.label}</span>
                        {relativeTime(project.updated_at)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
