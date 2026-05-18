"use client";

import { useMemo, useState } from "react";
import {
  estimateEnrichmentCostUsd,
  estimatePendingEnrichmentTokens,
  formatTokenCount,
  formatUsd,
  type EnrichmentTokenBreakdown,
} from "@/lib/token-estimate";

export type ModerationEstimateRow = {
  id: string;
  rawClaimText: string;
  sourceUrlCount?: number;
  processingStatus: string;
};

type Props = {
  rows: ModerationEstimateRow[];
};

const REPROCESS_STATUSES = new Set(["failed", "revision_requested"]);

function rowEstimate(row: ModerationEstimateRow): EnrichmentTokenBreakdown {
  return estimatePendingEnrichmentTokens({
    rawClaimText: row.rawClaimText,
    sourceUrlCount: row.sourceUrlCount,
  });
}

export function ModerationTokenEstimator({ rows }: Props) {
  const [expanded, setExpanded] = useState(false);

  const { queueTotal, queueCost, pendingReprocess } = useMemo(() => {
    let total = 0;
    let reprocess = 0;
    for (const row of rows) {
      const est = rowEstimate(row);
      total += est.total;
      if (REPROCESS_STATUSES.has(row.processingStatus)) {
        reprocess += est.total;
      }
    }
    return {
      queueTotal: total,
      queueCost: estimateEnrichmentCostUsd(total),
      pendingReprocess: reprocess,
    };
  }, [rows]);

  if (rows.length === 0) {
    return null;
  }

  return (
    <section
      className="rounded border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm"
      aria-label="OpenAI token usage estimates"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[var(--fg)]">
          <span className="font-medium">Queue ballpark:</span>{" "}
          {formatTokenCount(queueTotal)} tokens ({formatUsd(queueCost)}) across {rows.length}{" "}
          {rows.length === 1 ? "item" : "items"}
        </p>
        <button
          type="button"
          className="text-xs font-medium text-[var(--accent)] hover:underline"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? "Hide breakdown" : "How we estimate"}
        </button>
      </div>
      {pendingReprocess > 0 && (
        <p className="mt-1 text-xs text-[var(--muted)]">
          Failed / revision rows may cost another {formatTokenCount(pendingReprocess)} if reprocessed.
        </p>
      )}
      {expanded && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-[var(--muted)]">
          <li>
            One enrichment run: claim embedding, canonicalization, ~{formatTokenCount(10_000)} retrieved
            context (typical), verdict + confidence JSON calls, evidence summary.
          </li>
          <li>Each source URL adds ~4 embedding calls (document + chunks).</li>
          <li>
            Uses the same ~4 chars/token and completion reserves as backend budget pre-checks; actual
            usage is usually lower.
          </li>
          <li>
            Dev defaults (if budgets enabled): 200k tokens/day, 80k per pending claim scope — see{" "}
            <code className="text-[10px]">OPENAI_MAX_TOKENS_*</code> in README.
          </li>
        </ul>
      )}
    </section>
  );
}

/** Inline estimate for a single queue row. */
export function ModerationRowTokenHint({
  rawClaimText,
  sourceUrlCount,
}: {
  rawClaimText: string;
  sourceUrlCount?: number;
}) {
  const est = estimatePendingEnrichmentTokens({
    rawClaimText,
    sourceUrlCount,
  });
  const cost = estimateEnrichmentCostUsd(est.total);
  return (
    <span className="text-[var(--muted)]" title="Ballpark if enrichment runs or re-runs">
      Est. {formatTokenCount(est.total)} tokens ({formatUsd(cost)}) per enrichment
    </span>
  );
}
