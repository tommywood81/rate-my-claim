import Link from "next/link";

import { SearchForm } from "@/components/search-form";
import { serverGetEnvelope } from "@/lib/api-server";
import type { ClaimListItem } from "@/lib/types";

async function fetchRecentClaims(): Promise<ClaimListItem[]> {
  const { data } = await serverGetEnvelope<ClaimListItem[]>("/api/v1/claims?limit=8", {
    next: { revalidate: 30 },
  });
  return data;
}

export default async function Home() {
  const claims = await fetchRecentClaims();

  return (
    <div className="space-y-10">
      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight">Semantic claim intelligence</h1>
        <p className="mt-2 max-w-2xl text-[var(--muted)]">
          Submit empirical claims, review evidence-backed analyses, and explore a durable claim graph. AI assists;
          evidence and moderation stay authoritative.
        </p>
        <SearchForm className="mt-6" />
      </section>

      <section aria-labelledby="recent-claims-heading">
        <h2 id="recent-claims-heading" className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Recent claims
        </h2>
        <ul className="mt-3 divide-y divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)] shadow-sm">
          {claims.length === 0 && (
            <li className="px-4 py-6 text-sm text-[var(--muted)]">No public claims yet. Submit one to begin.</li>
          )}
          {claims.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <Link href={`/claims/${c.public_slug}`} className="font-medium text-[var(--fg)] hover:underline">
                {c.canonical_claim_text}
              </Link>
              <span className="shrink-0 text-xs text-[var(--muted)]">score {c.discovery_score}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm">
          <Link href="/claims" className="text-[var(--accent)] underline">
            Browse all claims
          </Link>
        </p>
      </section>
    </div>
  );
}
