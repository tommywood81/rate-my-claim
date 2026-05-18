import Link from "next/link";

type Claim = {
  id: string;
  public_slug: string;
  canonical_claim_text: string;
  confidence_score: number;
  discovery_score: number;
  scores?: { final_score: number };
};

export default async function BrowseClaimsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; cursor?: string }>;
}) {
  const sp = await searchParams;
  const base = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";
  const params = new URLSearchParams({ limit: "20" });
  if (sp.q) params.set("q", sp.q);
  if (sp.cursor) params.set("cursor", sp.cursor);
  const url = sp.q
    ? `${base}/api/v1/search/claims?${params}`
    : `${base}/api/v1/claims?limit=20`;
  const res = await fetch(url, { next: { revalidate: 15 } });
  const body = res.ok ? await res.json() : { data: [], meta: {} };
  const claims = (body.data || []) as Claim[];
  const meta = (body.meta || {}) as { has_more?: boolean; next_cursor?: string };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{sp.q ? `Search: ${sp.q}` : "Browse claims"}</h1>
      <ul className="divide-y divide-[var(--border)] rounded border border-[var(--border)] bg-[var(--card)]">
        {claims.map((c) => (
          <li key={c.id} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <Link href={`/claims/${c.public_slug}`} className="font-medium">
              {c.canonical_claim_text}
            </Link>
            <div className="text-xs text-[var(--muted)]">
              conf {c.confidence_score.toFixed(2)} · discovery {c.discovery_score}
              {c.scores?.final_score != null && (
                <> · relevance {c.scores.final_score.toFixed(2)}</>
              )}
            </div>
          </li>
        ))}
        {claims.length === 0 && <li className="px-4 py-6 text-sm text-[var(--muted)]">No results.</li>}
      </ul>
      {sp.q && meta.has_more && meta.next_cursor && (
        <p className="text-sm">
          <Link
            href={`/claims?q=${encodeURIComponent(sp.q)}&cursor=${encodeURIComponent(meta.next_cursor)}`}
            className="text-[var(--accent)] underline"
          >
            Load more results
          </Link>
        </p>
      )}
    </div>
  );
}
