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
        <p className="owid-kicker">Rate My Claim</p>
        <h1 className="owid-page-heading mt-3 max-w-3xl">Claims with receipts</h1>
        <p className="owid-lead mt-4 max-w-2xl">
          Knowledge shouldn&apos;t be a single answer. It should be a living, evidence-backed object.
        </p>

        <div className="mt-8 max-w-2xl space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-[var(--accent-dark)]">One claim. One page.</h2>
            <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-[var(--fg)]">
              <li>
                Every claim is a living record — built from sources, counterpoints, and evolving evidence.
              </li>
              <li>
                Claims are continuously re-checked as new information appears, not generated once and forgotten.
              </li>
              <li>
                As evidence shifts, claims can be updated, disputed, or overturned — keeping the system aligned
                with what&apos;s actually supported.
              </li>
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold text-[var(--accent-dark)]">Under the hood</h2>
            <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-[var(--fg)]">
              <li>
                Each claim lives in a structured data model and is embedded in semantic space alongside related
                claims.
              </li>
              <li>
                Explore how claims connect, cluster, and contradict each other — and track how truth status
                changes over time.{" "}
                <Link href="/atlas" className="font-medium text-[var(--accent)] hover:underline">
                  Open the claim map
                </Link>
                .
              </li>
            </ul>
          </div>
        </div>

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
          <p className="mt-1 text-sm text-[var(--muted)]">Living records in the library</p>
        </div>
        <div className="owid-card-padded text-center sm:text-left">
          <p className="owid-display text-3xl text-[var(--accent-dark)]">Live</p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            One claim, one page — published immediately, assessed in the background
          </p>
        </div>
        <div className="owid-card-padded text-center sm:text-left">
          <p className="owid-display text-3xl text-[var(--accent-dark)]">Evolving</p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Truth status can shift as new sources arrive and claims are re-checked
          </p>
        </div>
      </section>

      <section aria-labelledby="recent-claims-heading">
        <h2 id="recent-claims-heading" className="owid-section-heading">
          Recently updated
        </h2>
        <ul className="owid-card-list mt-4">
          {claims.length === 0 && (
            <li className="px-5 py-8 text-center text-sm text-[var(--muted)]">
              Nothing here yet.{" "}
              <Link href="/submit" className="font-medium text-[var(--accent)]">
                Submit the first claim
              </Link>
              .
            </li>
          )}
          {claims.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-[var(--bg-subtle)]">
              <Link
                href={`/claims/${c.public_slug}`}
                className="font-medium leading-snug text-[var(--fg)] no-underline hover:text-[var(--accent)] hover:underline"
              >
                {c.canonical_claim_text}
              </Link>
              {c.visibility_label ? (
                <span className="shrink-0 owid-badge">{c.visibility_label}</span>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
