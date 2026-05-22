import type { Metadata } from "next";

import { ClaimAtlasView } from "@/components/claim-atlas-view";

export const metadata: Metadata = {
  title: "Data model — claim embedding space",
  description:
    "Explore published claims projected from semantic embeddings into 3D. Watch the archive grow as more claims are indexed.",
};

export default function AtlasPage() {
  return (
    <main id="main-content" className="mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10">
      <p className="owid-kicker">Embedding atlas</p>
      <h1 className="owid-display mt-2 text-3xl sm:text-4xl">Data model</h1>
      <p className="owid-lead mt-3">
        Each point is a published claim positioned by a 3D PCA projection of its stored embedding vector. Clusters
        emerge as the corpus grows — similar wording and topics drift together even before moderators attach
        citations.
      </p>
      <div className="mt-8">
        <ClaimAtlasView />
      </div>
    </main>
  );
}
