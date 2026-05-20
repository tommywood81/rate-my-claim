import Link from "next/link";

import type { ClaimListItem } from "@/lib/types";

type ClaimSearchHitProps = {
  claim: ClaimListItem;
  showScores?: boolean;
};

export function ClaimSearchHit({ claim, showScores = false }: ClaimSearchHitProps) {
  const scores = claim.scores;
  return (
    <article className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-1">
        <h2 className="text-base font-medium leading-snug">
          <Link
            href={`/claims/${claim.public_slug}`}
            className="text-[var(--accent-dark)] no-underline hover:text-[var(--accent)] hover:underline"
          >
            {claim.canonical_claim_text}
          </Link>
        </h2>
        <p className="mt-1 text-xs text-[var(--muted)]">
          {claim.visibility_label && (
            <>
              <span className="font-medium text-[var(--fg)]">{claim.visibility_label}</span>
              {" · "}
            </>
          )}
          <span className="capitalize">{claim.status}</span>
          {" · "}
          confidence {claim.confidence_score.toFixed(2)}
          {" · "}
          {claim.evidence_count} evidence
          {" · "}
          discovery {claim.discovery_score}
        </p>
      </div>
      {showScores && scores && (
        <dl className="owid-card shrink-0 px-3 py-2 text-xs text-[var(--muted)]">
          <div className="flex justify-between gap-4">
            <dt>Relevance</dt>
            <dd className="font-medium text-[var(--fg)]">{scores.final_score.toFixed(2)}</dd>
          </div>
          <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5">
            <div>
              <dt>Semantic</dt>
              <dd>{scores.semantic_similarity.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Text</dt>
              <dd>{scores.text_relevance.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>{scores.evidence_quality.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Freshness</dt>
              <dd>{scores.freshness_score.toFixed(2)}</dd>
            </div>
          </div>
        </dl>
      )}
    </article>
  );
}
