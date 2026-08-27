"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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
  const [query, setQuery] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? projects.filter((p) => p.title.toLowerCase().includes(q)) : projects;
  }, [projects, query]);

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text)]"
      >
        Sessions ({projects.length})
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-10 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-2 shadow-xl"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              onNewSession();
              setOpen(false);
            }}
            className="mb-1 w-full rounded-md px-2 py-1.5 text-left text-sm font-medium text-[var(--mode-accent)] hover:bg-[var(--surface)]"
          >
            + New session
          </button>

          {projects.length > 6 ? (
            <input
              autoFocus
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter sessions…"
              className="mb-1 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm outline-none focus:border-[var(--mode-accent)]"
            />
          ) : null}

          {filtered.length === 0 ? (
            <p className="px-2 py-2 text-xs text-[var(--text-muted)]">
              {projects.length === 0 ? "No sessions yet." : "No matches."}
            </p>
          ) : (
            <ul className="max-h-80 overflow-y-auto">
              {filtered.map((project) => {
                const style = modeStyle(project.current_mode);
                const active = project.project_id === currentProjectId;
                return (
                  <li key={project.project_id}>
                    <button
                      type="button"
                      role="menuitem"
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
