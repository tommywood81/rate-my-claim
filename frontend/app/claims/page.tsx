import Link from "next/link";

type Claim = {
  id: string;
  public_slug: string;
  canonical_claim_text: string;
  confidence_score: number;
  discovery_score: number;
};

export default async function BrowseClaimsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const sp = await searchParams;
  const base = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";
  const url = sp.q
    ? `${base}/api/v1/search/claims?q=${encodeURIComponent(sp.q)}&limit=20`
    : `${base}/api/v1/claims?limit=20`;
  const res = await fetch(url, { next: { revalidate: 15 } });
  const body = res.ok ? await res.json() : { data: [] };
  const claims = (body.data || []) as Claim[];

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
            </div>
          </li>
        ))}
        {claims.length === 0 && <li className="px-4 py-6 text-sm text-[var(--muted)]">No results.</li>}
      </ul>
    </div>
  );
}
