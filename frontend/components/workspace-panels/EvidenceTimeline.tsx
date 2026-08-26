import type { EvidenceItem, EvidenceKind } from "@/lib/types";

const KIND_COLOR: Record<EvidenceKind, string> = {
  fact: "#5cd68a",
  inference: "#63c7ff",
  hypothesis: "#b98bff",
};

export default function EvidenceTimeline({ evidence }: { evidence: EvidenceItem[] }) {
  const sorted = [...evidence].sort(
    (a, b) => new Date(b.captured_at ?? 0).getTime() - new Date(a.captured_at ?? 0).getTime(),
  );

  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="mb-3 text-sm font-semibold text-[var(--text-muted)]">Evidence</h2>

      {sorted.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]">No evidence captured yet.</p>
      ) : (
        <ul className="space-y-2">
          {sorted.map((item) => (
            <li
              key={item.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] p-2.5"
            >
              <span
                className="mb-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium"
                style={{ color: KIND_COLOR[item.kind], backgroundColor: `${KIND_COLOR[item.kind]}22` }}
              >
                {item.kind}
              </span>
              <p className="text-sm">{item.claim}</p>
              {item.source_url ? (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-0.5 block truncate text-xs text-[var(--mode-accent)] hover:underline"
                >
                  {item.source_title || item.source_url}
                </a>
              ) : null}
              {item.notes ? (
                <p className="mt-0.5 text-xs text-[var(--text-muted)]">{item.notes}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
