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
      <p className="owid-kicker">Under the hood</p>
      <h1 className="owid-display mt-2 text-3xl sm:text-4xl">Claim map</h1>
      <p className="owid-lead mt-3">
        Each point is a published claim, positioned in semantic space alongside related statements. Clusters show
        where wording and topics overlap; distance hints at difference. Similar claims can still contradict each
        other — open a dot for sources and current truth status, or track how assessments change over time.
      </p>
      <div className="mt-8">
        <ClaimAtlasView />
      </div>
    </main>
  );
}
