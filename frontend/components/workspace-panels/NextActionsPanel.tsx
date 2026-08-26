import type { NextAction } from "@/lib/types";

export default function NextActionsPanel({ nextActions }: { nextActions: NextAction[] }) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">Next actions</h2>

      {nextActions.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">No next actions planned yet.</p>
      ) : (
        <ul className="space-y-2">
          {nextActions.map((action) => (
            <li
              key={action.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-2.5"
            >
              <div className="flex items-start justify-between gap-2">
                <p className={`text-sm ${action.completed ? "text-[var(--text-muted)] line-through" : ""}`}>
                  {action.description}
                </p>
                <span className="shrink-0 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
                  {action.time_box_minutes}m
                </span>
              </div>
              {action.success_signal ? (
                <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                  Success: {action.success_signal}
                </p>
              ) : null}
              {action.failure_signal ? (
                <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                  Failure: {action.failure_signal}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
