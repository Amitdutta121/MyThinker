import type { Decision } from "@/lib/types";

export default function DecisionHistory({ decisions }: { decisions: Decision[] }) {
  const sorted = [...decisions].sort(
    (a, b) => new Date(b.decided_at ?? 0).getTime() - new Date(a.decided_at ?? 0).getTime(),
  );

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">Decisions</h2>

      {sorted.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">No decisions made yet.</p>
      ) : (
        <ul className="space-y-2">
          {sorted.map((decision) => (
            <li
              key={decision.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-2.5"
            >
              <p className="text-xs text-[var(--text-muted)]">{decision.question}</p>
              <p className="text-sm font-medium">{decision.choice}</p>
              {decision.rationale ? (
                <p className="mt-0.5 text-xs text-[var(--text-muted)]">{decision.rationale}</p>
              ) : null}
              <span
                className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs ${
                  decision.reversible
                    ? "bg-[var(--mode-accent-soft)] text-[var(--mode-accent)]"
                    : "bg-red-500/10 text-red-300"
                }`}
              >
                {decision.reversible ? "reversible" : "irreversible"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
