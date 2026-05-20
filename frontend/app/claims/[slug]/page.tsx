import type { Metadata } from "next";

import { ClaimPageClient } from "@/components/claim-page-client";
import { serverGet } from "@/lib/api-server";
import type { ClaimDetail, ClaimGraph, ClaimTimeline as ClaimTimelineData } from "@/lib/types";

export const dynamic = "force-dynamic";

async function load(slug: string): Promise<ClaimDetail | null> {
  return serverGet<ClaimDetail>(`/api/v1/claims/${encodeURIComponent(slug)}`, { cache: "no-store" });
}

async function loadGraph(slug: string): Promise<ClaimGraph | null> {
  return serverGet<ClaimGraph>(
    `/api/v1/claims/${encodeURIComponent(slug)}/graph?depth=1&include_evidence_clusters=true`,
    { cache: "no-store" },
  );
}

async function loadTimeline(slug: string): Promise<ClaimTimelineData | null> {
  return serverGet<ClaimTimelineData>(`/api/v1/claims/${encodeURIComponent(slug)}/timeline`, {
    cache: "no-store",
  });
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const d = await load(slug);
  if (!d) return { title: "Claim" };
  return {
    title: d.canonical_claim_text.slice(0, 70),
    description: d.canonical_claim_text.slice(0, 160),
    openGraph: { title: d.canonical_claim_text, type: "article" },
  };
}

export default async function ClaimPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [d, graph, timeline] = await Promise.all([load(slug), loadGraph(slug), loadTimeline(slug)]);
  if (!d) {
    return (
      <p className="text-sm text-[var(--muted)]" role="status">
        Claim not found.
      </p>
    );
  }

  return <ClaimPageClient slug={slug} initial={d} graph={graph} timeline={timeline} />;
}
