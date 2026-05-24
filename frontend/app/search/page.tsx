import type { Metadata } from "next";
import Link from "next/link";

import { ClaimSearchHit } from "@/components/claim-search-hit";
import { SearchForm } from "@/components/search-form";
import { serverGetEnvelope } from "@/lib/api-server";
import type { ClaimListItem, CursorMeta } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}): Promise<Metadata> {
  const { q } = await searchParams;
  if (!q?.trim()) {
    return { title: "Search claims" };
  }
  return {
    title: `Search: ${q.slice(0, 60)}`,
    description: `Search results for “${q.slice(0, 120)}”.`,
  };
}

const SORTS = [
  { id: "relevance", label: "Relevance" },
  { id: "confidence", label: "Confidence" },
  { id: "freshness", label: "Freshness" },
  { id: "evidence", label: "Evidence" },
] as const;

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; cursor?: string; sort?: string; status?: string }>;
}) {
  const sp = await searchParams;
  const q = sp.q?.trim() ?? "";
  const sort = sp.sort || "relevance";

  let claims: ClaimListItem[] = [];
  let meta: CursorMeta = {};

  if (q) {
    const params = new URLSearchParams({ q, limit: "20", sort });
    if (sp.cursor) params.set("cursor", sp.cursor);
    if (sp.status) params.set("status", sp.status);
    const result = await serverGetEnvelope<ClaimListItem[]>(
      `/api/v1/search/claims?${params}`,
      { cache: "no-store" },
    );
    claims = result.data;
    meta = result.meta as CursorMeta;
  }

  return (
    <div className="space-y-8">
      <header className="space-y-3 border-b border-[var(--border)] pb-6">
        <p className="owid-kicker">Explore</p>
        <h1 className="owid-page-heading text-3xl sm:text-4xl">Search claims</h1>
        <p className="owid-lead text-base">
          Search the claim library by meaning — claims live in semantic space alongside related statements. Results
          weigh similarity, source quality, and how recently the truth status was assessed.
        </p>
      </header>

      <SearchForm defaultQuery={q} />

      {q && (
        <nav className="flex flex-wrap gap-2 text-sm" aria-label="Sort results">
          {SORTS.map((s) => {
            const active = sort === s.id;
            const href = `/search?${new URLSearchParams({ q, sort: s.id }).toString()}`;
            return (
              <Link
                key={s.id}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`owid-chip focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${
                  active ? "owid-chip-active" : ""
                }`}
              >
                {s.label}
              </Link>
            );
          })}
        </nav>
      )}

      {!q && (
        <p className="text-sm text-[var(--muted)]">
          Search by question or claim wording — we surface close matches in the library.
        </p>
      )}

      {q && (
        <section aria-labelledby="search-results-heading">
          <h2 id="search-results-heading" className="sr-only">
            Results for {q}
          </h2>
          <ul className="owid-card-list">
            {claims.map((c) => (
              <li key={c.id}>
                <ClaimSearchHit claim={c} showScores />
              </li>
            ))}
            {claims.length === 0 && (
              <li className="px-4 py-8 text-center text-sm text-[var(--muted)]">No matching claims.</li>
            )}
          </ul>
          {meta.has_more && meta.next_cursor && (
            <p className="mt-4 text-sm">
              <Link
                href={`/search?${new URLSearchParams({
                  q,
                  sort,
                  cursor: meta.next_cursor,
                }).toString()}`}
                className="font-medium text-[var(--accent)] underline"
              >
                Load more results
              </Link>
            </p>
          )}
        </section>
      )}
    </div>
  );
}
