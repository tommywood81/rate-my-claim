/**
 * Ballpark OpenAI token/cost estimates for pending-claim enrichment.
 * Mirrors backend pre-flight logic (~4 chars/token, conservative completion reserves).
 */

const CHARS_PER_TOKEN = 4;

const CANONICALIZE_SYSTEM =
  "You normalize empirical claims for a research database. Output strict JSON keys: canonical_text (string), normalized_text (string), domain_guess (string or null), rejection_reason (string or null if acceptable). Reject vague, ideological, or non-falsifiable claims with rejection_reason.";

const VERDICT_SYSTEM =
  "You assist a moderation queue. Using ONLY numbered lines in CONTEXT, produce JSON: {\"verdict_summary\": string, \"citations\": [{\"context_line\": int, \"note\": string}], \"confidence_hint\": number, \"controversy_hint\": number }. Never invent URLs or studies not present in CONTEXT.";

const CONFIDENCE_SYSTEM =
  "Score evidence support strength (not absolute truth). JSON keys: aggregate (0-1), evidence_quality, source_credibility, evidence_consistency, freshness, rationale (string).";

const SUMMARY_SYSTEM = "Summarize retrieved evidence in <=120 words. Do not invent sources.";

/** Typical retrieved DB + URL context size used during enrichment (chars). */
const TYPICAL_CONTEXT_CHARS = 10_000;

/** ~1 doc + 3 chunk embeddings per submitted source URL. */
const EMBEDDINGS_PER_SOURCE_URL = 4;

const COST_PER_1M: Record<string, { input: number; output: number }> = {
  "gpt-4o-mini": { input: 0.15, output: 0.6 },
  "gpt-4o": { input: 2.5, output: 10 },
  "text-embedding-3-small": { input: 0.02, output: 0 },
};

export type EnrichmentTokenBreakdown = {
  embeddingClaim: number;
  canonicalize: number;
  sourceUrlEmbeddings: number;
  structuredVerdict: number;
  confidenceAnalysis: number;
  evidenceSummary: number;
  total: number;
};

export function estimateEmbeddingTokens(text: string): number {
  const len = Math.min(text.length, 8192);
  return Math.max(1, Math.floor(len / CHARS_PER_TOKEN) + 64);
}

export function estimateChatTokens(
  system: string,
  user: string,
  completionReserve: number,
): number {
  return Math.max(
    1,
    Math.floor(system.length / CHARS_PER_TOKEN) +
      Math.floor(user.length / CHARS_PER_TOKEN) +
      completionReserve,
  );
}

export type PendingEnrichmentInput = {
  rawClaimText: string;
  sourceUrlCount?: number;
};

/** Upper-bound style estimate for one full enrichment + reprocess run. */
export function estimatePendingEnrichmentTokens(
  input: PendingEnrichmentInput,
): EnrichmentTokenBreakdown {
  const raw = input.rawClaimText.slice(0, 8000);
  const urlCount = Math.max(0, input.sourceUrlCount ?? 0);

  const embeddingClaim = estimateEmbeddingTokens(raw);

  const canonicalize = estimateChatTokens(CANONICALIZE_SYSTEM, raw, 3072);

  const perUrlEmbed = estimateEmbeddingTokens(" ".repeat(2000));
  const sourceUrlEmbeddings = urlCount * EMBEDDINGS_PER_SOURCE_URL * perUrlEmbed;

  const contextChars = Math.min(16_000, TYPICAL_CONTEXT_CHARS + raw.length);
  const contextBlock = "x".repeat(contextChars);
  const verdictUser = `CLAIM:\n${raw}\n\nCONTEXT:\n${contextBlock}`;
  const structuredVerdict = estimateChatTokens(VERDICT_SYSTEM, verdictUser, 3072);

  const digestChars = Math.min(12_000, contextChars);
  const confidenceUser = `Claim: ${raw}\nDigest:\n${"x".repeat(digestChars)}`;
  const confidenceAnalysis = estimateChatTokens(CONFIDENCE_SYSTEM, confidenceUser, 3072);

  const summaryCtx = Math.min(8000, contextChars);
  const evidenceSummary = estimateChatTokens(SUMMARY_SYSTEM, "x".repeat(summaryCtx), 512);

  const total =
    embeddingClaim +
    canonicalize +
    sourceUrlEmbeddings +
    structuredVerdict +
    confidenceAnalysis +
    evidenceSummary;

  return {
    embeddingClaim,
    canonicalize,
    sourceUrlEmbeddings,
    structuredVerdict,
    confidenceAnalysis,
    evidenceSummary,
    total,
  };
}

/** Rough USD assuming mostly gpt-4o-mini chat + embedding-small (50/50 split ballpark). */
export function estimateEnrichmentCostUsd(totalTokens: number): number {
  const embedShare = 0.12;
  const embedTokens = totalTokens * embedShare;
  const chatTokens = totalTokens - embedTokens;
  const embedCost = (embedTokens / 1_000_000) * COST_PER_1M["text-embedding-3-small"].input;
  const chatIn = (chatTokens * 0.7) / 1_000_000;
  const chatOut = (chatTokens * 0.3) / 1_000_000;
  const chatCost =
    chatIn * COST_PER_1M["gpt-4o-mini"].input + chatOut * COST_PER_1M["gpt-4o-mini"].output;
  return embedCost + chatCost;
}

export function formatTokenCount(n: number): string {
  if (n >= 1_000_000) {
    return `~${(n / 1_000_000).toFixed(1)}M`;
  }
  if (n >= 1000) {
    return `~${Math.round(n / 1000)}k`;
  }
  return `~${n}`;
}

export function formatUsd(n: number): string {
  if (n < 0.01) {
    return `<$0.01`;
  }
  if (n < 1) {
    return `~$${n.toFixed(2)}`;
  }
  return `~$${n.toFixed(2)}`;
}
