"use client";

import { patchNorthStar } from "@/lib/api-client";
import type { ProjectState } from "@/lib/types";
import InlineEdit from "./InlineEdit";

/**
 * The one always-visible anchor: what the user is working toward. Backed by
 * `north_star.title`; edits go straight to `PATCH /north-star`, no agent turn.
 */
export default function GoalLine({
  projectId,
  title,
  onStateChange,
}: {
  projectId: string;
  title: string;
  onStateChange: (next: ProjectState) => void;
}) {
  return (
    <section className="border-b border-[var(--border)] px-1 pb-3">
      <p className="mb-1 text-xs font-medium text-[var(--text-muted)]">Goal</p>
      <InlineEdit
        value={title}
        ariaLabel="Edit the goal"
        placeholder="Name what you're working toward"
        className="text-base font-semibold leading-snug"
        onSave={async (next) => {
          onStateChange(await patchNorthStar(projectId, { title: next }));
        }}
      />
    </section>
  );
}
