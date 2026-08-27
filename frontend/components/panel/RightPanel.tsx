"use client";

import { useState } from "react";
import type { ProjectState } from "@/lib/types";
import { sessionToMarkdown } from "@/lib/session-markdown";
import Icon from "../Icon";
import GoalLine from "./GoalLine";
import RiskLine from "./RiskLine";
import PlanDocument from "./PlanDocument";
import DecisionsList from "./DecisionsList";
import WorkingNotesDrawer from "./WorkingNotesDrawer";

function PanelSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-hidden>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
        >
          <div className="h-3 w-24 animate-pulse rounded bg-[var(--surface-raised)]" />
          <div className="mt-3 h-3 w-full animate-pulse rounded bg-[var(--surface-raised)]" />
          <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-[var(--surface-raised)]" />
        </div>
      ))}
    </div>
  );
}

function ChangeRibbon({
  change,
  onDismiss,
}: {
  change: string[];
  onDismiss?: () => void;
}) {
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-xl border border-[var(--mode-accent)] bg-[var(--surface)] px-3 py-2 text-xs"
      style={{ boxShadow: "0 0 0 1px var(--mode-accent)" }}
    >
      <span className="mt-0.5 shrink-0 font-semibold text-[var(--mode-accent)]">Updated</span>
      <span className="flex flex-wrap gap-x-1.5 gap-y-1 text-[var(--text)]">
        {change.map((entry, index) => (
          <span key={index}>
            {entry}
            {index < change.length - 1 ? (
              <span className="text-[var(--text-muted)]"> ·</span>
            ) : null}
          </span>
        ))}
      </span>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="ml-auto shrink-0 rounded p-0.5 text-[var(--text-muted)] hover:text-[var(--text)]"
        >
          <Icon name="close" size={12} />
        </button>
      ) : null}
    </div>
  );
}

function CopySessionButton({ state }: { state: ProjectState }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(sessionToMarkdown(state));
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable — nothing to do */
        }
      }}
      className="self-end rounded border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-muted)] hover:text-[var(--text)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--mode-accent)]"
    >
      {copied ? "Copied" : "Copy session as Markdown"}
    </button>
  );
}

/**
 * The right panel, "Document & ledger" layout: one scroll of Goal → risk line →
 * Plan (as a document) → Decisions (approve / edit / delete) → the agent's
 * working-notes drawer. Direct edits post straight to the API and lift the
 * returned `ProjectState` via `onStateChange`.
 */
export default function RightPanel({
  projectState,
  loading,
  change = [],
  onDismissChange,
  onPrefillComposer,
  onStateChange,
}: {
  projectState: ProjectState | null;
  loading: boolean;
  change?: string[];
  onDismissChange?: () => void;
  onPrefillComposer?: (text: string) => void;
  onStateChange: (next: ProjectState) => void;
}) {
  if (loading) {
    return <PanelSkeleton />;
  }

  if (!projectState) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--text-muted)]">
        Your goal, the plan, and the decisions you make show up here as you think.
      </div>
    );
  }

  // Always present on a persisted state; the generated schema marks it optional
  // because the backend default is a factory.
  const projectId = projectState.project_id as string;

  return (
    <div className="flex flex-col gap-4">
      {change.length > 0 ? (
        <ChangeRibbon change={change} onDismiss={onDismissChange} />
      ) : null}

      <GoalLine
        projectId={projectId}
        title={projectState.north_star?.title ?? ""}
        onStateChange={onStateChange}
      />
      <RiskLine state={projectState} onPrefillComposer={onPrefillComposer} />
      <PlanDocument
        projectId={projectId}
        state={projectState}
        onStateChange={onStateChange}
      />
      <DecisionsList
        projectId={projectId}
        state={projectState}
        onStateChange={onStateChange}
        onPrefillComposer={onPrefillComposer}
      />
      <WorkingNotesDrawer state={projectState} />

      <div className="flex justify-end">
        <CopySessionButton state={projectState} />
      </div>
    </div>
  );
}
