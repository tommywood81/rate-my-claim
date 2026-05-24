import type { Metadata } from "next";

import { ClaimAtlasView } from "@/components/claim-atlas-view";

export const metadata: Metadata = {
  title: "Claim map",
  description:
    "Explore published claims in 3D — similar wording clusters together. Click a dot, open the page, argue properly.",
};

export default function AtlasPage() {
  return (
    <main id="main-content" className="mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10">
      <p className="owid-kicker">Claim map</p>
      <h1 className="owid-display mt-2 text-3xl sm:text-4xl">See the neighbourhood</h1>
      <p className="owid-lead mt-3">
        Each dot is a published claim. Similar statements drift together in 3D — useful for spotting clusters,
        outliers, and claims that sound alike but ended up on opposite sides. Fullscreen if you want the lab
        coat experience; it auto-rotates when you stare too long.
      </p>
      <div className="mt-8">
        <ClaimAtlasView />
      </div>
    </main>
  );
}
