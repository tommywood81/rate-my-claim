import Link from "next/link";

import type { ClaimListItem } from "@/lib/types";

type ClaimSearchHitProps = {
  claim: ClaimListItem;
  showScores?: boolean;
};

export function ClaimSearchHit({ claim, showScores = false }: ClaimSearchHitProps) {
  const scores = claim.scores;
  const meta: string[] = [];
  if (claim.visibility_label) meta.push(claim.visibility_label);
  meta.push(`${claim.evidence_count} source${claim.evidence_count === 1 ? "" : "s"}`);
  meta.push(`confidence ${claim.confidence_score.toFixed(2)}`);

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
        <p className="mt-1 text-xs text-[var(--muted)]">{meta.join(" · ")}</p>
      </div>
      {showScores && scores && (
        <dl className="owid-card shrink-0 px-3 py-2 text-xs text-[var(--muted)]">
          <div className="flex justify-between gap-4">
            <dt>Match</dt>
            <dd className="font-medium text-[var(--fg)]">{scores.final_score.toFixed(2)}</dd>
          </div>
          <div className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5">
            <div>
              <dt>Meaning</dt>
              <dd>{scores.semantic_similarity.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Keywords</dt>
              <dd>{scores.text_relevance.toFixed(2)}</dd>
            </div>
            <div>
              <dt>Sources</dt>
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
