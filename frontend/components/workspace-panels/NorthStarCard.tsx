import type { NorthStar } from "@/lib/types";

function ChipList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="mb-1 text-xs uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, index) => (
          <span
            key={index}
            className="rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text)]"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function NorthStarCard({ northStar }: { northStar: NorthStar | null }) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="mb-2 text-sm font-semibold text-[var(--text-muted)]">North star</h2>
      {!northStar ? (
        <p className="text-sm text-[var(--text-muted)]">Nothing captured yet.</p>
      ) : (
        <div className="space-y-3">
          <p className="text-base font-medium">{northStar.title}</p>
          {northStar.problem_statement ? (
            <p className="text-sm text-[var(--text)]">{northStar.problem_statement}</p>
          ) : null}
          {northStar.current_hypothesis ? (
            <p className="text-sm text-[var(--text-muted)]">
              <span className="text-[var(--text)]">Hypothesis: </span>
              {northStar.current_hypothesis}
            </p>
          ) : null}
          {northStar.next_action ? (
            <p className="text-sm text-[var(--text-muted)]">
              <span className="text-[var(--text)]">Next: </span>
              {northStar.next_action}
            </p>
          ) : null}
          <ChipList label="Constraints" items={northStar.constraints ?? []} />
          <ChipList label="Success criteria" items={northStar.success_criteria ?? []} />
          <ChipList label="Non-goals" items={northStar.non_goals ?? []} />
        </div>
      )}
    </section>
  );
}
