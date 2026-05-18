import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ClaimSearchHit } from "@/components/claim-search-hit";
import { SearchForm } from "@/components/search-form";
import { serverGetEnvelope } from "@/lib/api-server";
import type { ClaimListItem, CursorMeta } from "@/lib/types";

export const metadata: Metadata = {
  title: "Browse claims",
  description: "Browse and filter published claims on Rate My Claim.",
};

export default async function BrowseClaimsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; cursor?: string }>;
}) {
  const sp = await searchParams;

  if (sp.q?.trim()) {
    const params = new URLSearchParams({ q: sp.q.trim() });
    if (sp.cursor) params.set("cursor", sp.cursor);
    redirect(`/search?${params}`);
  }

  const { data: claims, meta: rawMeta } = await serverGetEnvelope<ClaimListItem[]>(
    "/api/v1/claims?limit=20",
    { next: { revalidate: 15 } },
  );
  const meta = rawMeta as CursorMeta;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Browse claims</h1>
        <p className="text-sm text-[var(--muted)]">
          Published claims ordered by discovery. Use{" "}
          <Link href="/search" className="underline">
            search
          </Link>{" "}
          for hybrid semantic ranking.
        </p>
      </header>

      <SearchForm action="/search" />

      <ul className="divide-y divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--card)] shadow-sm">
        {claims.map((c) => (
          <li key={c.id}>
            <ClaimSearchHit claim={c} />
          </li>
        ))}
        {claims.length === 0 && (
          <li className="px-4 py-8 text-center text-sm text-[var(--muted)]">No public claims yet.</li>
        )}
      </ul>

      {meta.has_more && meta.next_cursor && (
        <p className="text-sm">
          <Link
            href={`/claims?cursor=${encodeURIComponent(String(meta.next_cursor))}`}
            className="font-medium text-[var(--accent)] underline"
          >
            Load more
          </Link>
        </p>
      )}
    </div>
  );
}
