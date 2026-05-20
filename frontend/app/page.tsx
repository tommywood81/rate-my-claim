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
  <>
      <section className="owid-hero">
        <p className="owid-kicker">Evidence-backed claim intelligence</p>
        <h1 className="owid-page-heading mt-3 max-w-3xl">
          Research and data to evaluate empirical claims
        </h1>
        <p className="owid-lead mt-4">
          Submit falsifiable claims, review cited evidence, and explore how statements relate in a durable claim graph.
          AI assists interpretation; evidence and moderation stay authoritative.
        </p>
        <SearchForm className="mt-8 max-w-2xl" large />
        <p className="mt-6 text-sm text-[var(--muted)]">
          <Link href="/submit" className="font-semibold text-[var(--accent-dark)]">
            Submit a claim
          </Link>
          {" · "}
          <Link href="/claims">Browse all claims</Link>
        </p>
      </section>

      <section className="mb-4 grid gap-4 sm:grid-cols-3">
        <div className="owid-card-padded text-center sm:text-left">
          <p className="owid-display text-3xl text-[var(--accent-dark)]">{claims.length || "—"}</p>
          <p className="mt-1 text-sm text-[var(--muted)]">Recent public claims</p>
        </div>
        <div className="owid-card-padded text-center sm:text-left">
          <p className="owid-display text-3xl text-[var(--accent-dark)]">Live</p>
          <p className="mt-1 text-sm text-[var(--muted)]">Claims visible while enrichment runs</p>
        </div>
        <div className="owid-card-padded text-center sm:text-left">
          <p className="owid-display text-3xl text-[var(--accent-dark)]">Open</p>
          <p className="mt-1 text-sm text-[var(--muted)]">Evidence-first, no engagement farming</p>
        </div>
      </section>

      <section aria-labelledby="recent-claims-heading">
        <h2 id="recent-claims-heading" className="owid-section-heading">
          Recently updated claims
        </h2>
        <ul className="owid-card-list mt-4">
          {claims.length === 0 && (
            <li className="px-5 py-8 text-center text-sm text-[var(--muted)]">No public claims yet. Submit one to begin.</li>
          )}
          {claims.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-[var(--bg-subtle)]">
              <Link
                href={`/claims/${c.public_slug}`}
                className="font-medium leading-snug text-[var(--fg)] no-underline hover:text-[var(--accent)] hover:underline"
              >
                {c.canonical_claim_text}
              </Link>
              <span className="shrink-0 owid-badge">discovery {c.discovery_score}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
