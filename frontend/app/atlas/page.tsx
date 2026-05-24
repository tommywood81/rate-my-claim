import type { Metadata } from "next";

import { ClaimAtlasView } from "@/components/claim-atlas-view";

export const metadata: Metadata = {
  title: "Claim map",
  description:
    "Explore how claims connect, cluster, and contradict in semantic space — and open any dot to see its truth status.",
};

export default function AtlasPage() {
  return (
    <main id="main-content" className="mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10">
      <p className="owid-kicker">Claim map</p>
      <h1 className="owid-display mt-2 text-3xl sm:text-4xl">See how claims cluster</h1>
      <p className="owid-lead mt-3">
        Each point is a published claim, positioned in semantic space alongside related statements. Clusters show
        where wording and topics overlap; distance hints at difference. Similar claims can still contradict each
        other — open a dot for sources and current truth status, or track how assessments change over time.
      </p>
      <div className="mt-8">
        <ClaimAtlasView />
      </div>

      <section className="mt-10 max-w-2xl border-t border-[var(--border)] pt-8">
        <h2 className="owid-kicker">Under the hood</h2>
        <p className="mt-3 text-sm leading-relaxed text-[var(--muted)]">
          Each claim is added to an embedding database with{" "}
          <strong className="font-medium text-[var(--fg)]">1,536 dimensions</strong>. That is impossible to
          visualise directly, so we use{" "}
          <strong className="font-medium text-[var(--fg)]">Principal Component Analysis (PCA)</strong> to compress
          those dimensions into <strong className="font-medium text-[var(--fg)]">X, Y, and Z</strong> coordinates
          — the three axes of this map.
        </p>
      </section>
    </main>
  );
}
