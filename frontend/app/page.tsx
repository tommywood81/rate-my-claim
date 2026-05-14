import Link from "next/link";

async function fetchClaims() {
  const res = await fetch(`${process.env.INTERNAL_API_URL || "http://127.0.0.1:8000"}/api/v1/claims?limit=8`, {
    next: { revalidate: 30 },
  });
  if (!res.ok) return [];
  const body = await res.json();
  return body.data as { id: string; public_slug: string; canonical_claim_text: string; discovery_score: number }[];
}

export default async function Home() {
  const claims = await fetchClaims();
  return (
    <div className="space-y-10">
      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight">Semantic claim intelligence</h1>
        <p className="mt-2 max-w-2xl text-[var(--muted)]">
          Submit empirical claims, review evidence-backed analyses, and explore a durable claim graph. AI assists;
          evidence and moderation stay authoritative.
        </p>
        <form className="mt-6 flex flex-col gap-2 sm:flex-row" action="/claims" method="get">
          <input
            name="q"
            placeholder="Search claims…"
            className="flex-1 rounded border border-[var(--border)] px-3 py-2"
          />
          <button
            type="submit"
            className="rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-95"
          >
            Search
          </button>
        </form>
      </section>
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Recent claims</h2>
        <ul className="mt-3 divide-y divide-[var(--border)] rounded border border-[var(--border)] bg-[var(--card)]">
          {claims.length === 0 && (
            <li className="px-4 py-6 text-sm text-[var(--muted)]">No public claims yet. Submit one to begin.</li>
          )}
          {claims.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <Link href={`/claims/${c.public_slug}`} className="font-medium text-[var(--fg)]">
                {c.canonical_claim_text}
              </Link>
              <span className="text-xs text-[var(--muted)]">score {c.discovery_score}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
