"use client";

import { motion } from "motion/react";
import type { BranchStatus, IdeaBranch } from "@/lib/types";

const LANES: { status: BranchStatus; label: string }[] = [
  { status: "active", label: "Active" },
  { status: "parked", label: "Parked" },
  { status: "merged", label: "Merged" },
  { status: "discarded", label: "Discarded" },
];

export default function BranchGraph({ branches }: { branches: IdeaBranch[] }) {
  const hasBranches = branches.length > 0;

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">Branches</h2>

      {!hasBranches ? (
        <p className="text-sm text-[var(--text-muted)]">No branches yet.</p>
      ) : (
        <div className="space-y-4">
          {LANES.map((lane) => {
            const laneBranches = branches.filter((branch) => branch.status === lane.status);
            if (laneBranches.length === 0) return null;
            return (
              <div key={lane.status} data-testid={`branch-lane-${lane.status}`}>
                <p className="mb-1.5 text-xs uppercase tracking-wide text-[var(--text-muted)]">
                  {lane.label}
                </p>
                <div className="flex flex-col gap-2 border-l-2 border-[var(--border)] pl-3">
                  {laneBranches.map((branch) => (
                    <motion.div
                      key={branch.id}
                      layout
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-2.5"
                    >
                      <p className="text-sm font-medium">{branch.name}</p>
                      {branch.summary ? (
                        <p className="mt-0.5 text-xs text-[var(--text-muted)]">{branch.summary}</p>
                      ) : null}
                      {branch.relationship_to_goal ? (
                        <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                          Relates to goal: {branch.relationship_to_goal}
                        </p>
                      ) : null}
                    </motion.div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
