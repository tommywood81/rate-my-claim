import type { EvidenceItem } from "@/lib/types";

type EvidenceListProps = {
  title: string;
  items: EvidenceItem[];
  variant?: "default" | "prominent";
};

function formatHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function EvidenceList({ title, items, variant = "default" }: EvidenceListProps) {
  if (!items.length) return null;

  const cardClass = variant === "prominent" ? "owid-card p-4 sm:p-5" : "owid-card p-3";

  const slug = title.replace(/\s+/g, "-").toLowerCase();

  return (
    <section aria-labelledby={`evidence-${slug}`}>
      <h3 id={`evidence-${slug}`} className="owid-kicker">
        {title} ({items.length})
      </h3>
      <ul className="mt-3 space-y-3">
        {items.map((e) => (
          <li key={e.id} className={cardClass}>
            <h4 className="font-medium leading-snug text-[var(--accent-dark)]">{e.title}</h4>
            {e.url && (
              <p className="mt-1.5 text-xs leading-relaxed text-[var(--muted)] break-all">
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--accent)] hover:underline"
                  title={e.url}
                >
                  {e.url}
                </a>
                <span className="mx-1.5 text-[var(--border)]" aria-hidden="true">
                  ·
                </span>
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-[var(--accent-dark)] hover:underline whitespace-nowrap"
                >
                  Open source ({formatHost(e.url)})
                </a>
              </p>
            )}
            {e.summary && (
              <p className="mt-3 text-sm leading-relaxed text-[var(--fg)]">
                <span className="sr-only">Saved excerpt: </span>
                {e.summary}
              </p>
            )}
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
                  <dd>Saved {new Date(e.retrieval_timestamp).toLocaleString()}</dd>
                </div>
              )}
            </dl>
          </li>
        ))}
      </ul>
    </section>
  );
}
