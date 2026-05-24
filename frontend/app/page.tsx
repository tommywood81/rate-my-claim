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
        <p className="owid-kicker">Better than asking a chatbot</p>
        <h1 className="owid-page-heading mt-3 max-w-3xl">
          Claims with receipts — that stick around
        </h1>
        <p className="owid-lead mt-4 max-w-2xl">
          A language model will give you a confident paragraph and forget you by lunch. We go find sources,
          line them up for and against, and leave the result on a page you (and everyone else) can revisit.
        </p>
        <ul className="mt-6 max-w-2xl space-y-2.5 text-sm leading-relaxed text-[var(--fg)]">
          <li className="flex gap-2">
            <span className="shrink-0 text-[var(--accent)]" aria-hidden>
              →
            </span>
            <span>
              <strong className="font-semibold">Real links, not vibes</strong> — your URLs plus claims already
              in the library, not whatever the model hallucinated last week
            </span>
          </li>
          <li className="flex gap-2">
            <span className="shrink-0 text-[var(--accent)]" aria-hidden>
              →
            </span>
            <span>
              <strong className="font-semibold">One claim, one page</strong> — submit and it goes live; scores
              and evidence fill in while the check runs
            </span>
          </li>
          <li className="flex gap-2">
            <span className="shrink-0 text-[var(--accent)]" aria-hidden>
              →
            </span>
            <span>
              <strong className="font-semibold">See the neighbours</strong> — search by meaning, browse
              contradictions, poke the 3D claim map when you feel nerdy
            </span>
          </li>
          <li className="flex gap-2">
            <span className="shrink-0 text-[var(--accent)]" aria-hidden>
              →
            </span>
            <span>
              <strong className="font-semibold">AI on a leash</strong> — models draft the write-up; the source
              list is what you actually argue about
            </span>
          </li>
        </ul>
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
          <p className="mt-1 text-sm text-[var(--muted)]">Claims in the library right now</p>
        </div>
        <div className="owid-card-padded text-center sm:text-left">
          <p className="owid-display text-3xl text-[var(--accent-dark)]">Live</p>
          <p className="mt-1 text-sm text-[var(--muted)]">Published instantly — the check catches up in the background</p>
        </div>
        <div className="owid-card-padded text-center sm:text-left">
          <p className="owid-display text-3xl text-[var(--accent-dark)]">No doomscroll</p>
          <p className="mt-1 text-sm text-[var(--muted)]">Evidence first. No outrage mechanics or engagement bait.</p>
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
