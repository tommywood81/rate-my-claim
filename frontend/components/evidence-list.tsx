import type { EvidenceItem } from "@/lib/types";

type EvidenceListProps = {
  title: string;
  items: EvidenceItem[];
  variant?: "default" | "prominent";
};

export function EvidenceList({ title, items, variant = "default" }: EvidenceListProps) {
  if (!items.length) return null;

  const cardClass =
    variant === "prominent"
      ? "rounded-lg border border-[var(--border)] bg-white p-4 shadow-sm"
      : "rounded border border-[var(--border)] bg-white p-3";

  const slug = title.replace(/\s+/g, "-").toLowerCase();

  return (
    <section aria-labelledby={`evidence-${slug}`}>
      <h3
        id={`evidence-${slug}`}
        className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]"
      >
        {title} ({items.length})
      </h3>
      <ul className="mt-3 space-y-3">
        {items.map((e) => (
          <li key={e.id} className={cardClass}>
            <h4 className="font-medium leading-snug text-[var(--fg)]">
              {e.url ? (
                <a href={e.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                  {e.title}
                </a>
              ) : (
                e.title
              )}
            </h4>
            {e.summary && <p className="mt-2 text-sm leading-relaxed text-[var(--fg)]">{e.summary}</p>}
            <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
              {e.publisher && (
                <div>
                  <dt className="sr-only">Publisher</dt>
                  <dd>{e.publisher}</dd>
                </div>
              )}
              <div>
                <dt className="sr-only">Credibility</dt>
                <dd>Credibility {e.credibility_score.toFixed(2)}</dd>
              </div>
              {e.retrieval_timestamp && (
                <div>
                  <dt className="sr-only">Retrieved</dt>
                  <dd>Retrieved {new Date(e.retrieval_timestamp).toLocaleString()}</dd>
                </div>
              )}
            </dl>
          </li>
        ))}
      </ul>
    </section>
  );
}
