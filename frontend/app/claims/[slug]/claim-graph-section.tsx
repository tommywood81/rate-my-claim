"use client";

import dynamic from "next/dynamic";

import type { ClaimGraph } from "@/lib/types";

const ClaimGraphPanel = dynamic(
  () => import("./claim-graph-panel").then((m) => m.ClaimGraphPanel),
  {
    ssr: false,
    loading: () => (
      <p className="text-sm text-[var(--muted)]" role="status">
        Loading relationship graph…
      </p>
    ),
  },
);

export function ClaimGraphSection({ slug, graph }: { slug: string; graph: ClaimGraph }) {
  return <ClaimGraphPanel slug={slug} initialGraph={graph} />;
}
