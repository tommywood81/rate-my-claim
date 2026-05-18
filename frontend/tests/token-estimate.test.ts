import { describe, expect, it } from "vitest";
import {
  estimateEmbeddingTokens,
  estimatePendingEnrichmentTokens,
  formatTokenCount,
} from "@/lib/token-estimate";

describe("token-estimate", () => {
  it("grows with claim length and source URLs", () => {
    const short = estimatePendingEnrichmentTokens({ rawClaimText: "Short claim text here." });
    const long = estimatePendingEnrichmentTokens({
      rawClaimText: "x".repeat(4000),
      sourceUrlCount: 2,
    });
    expect(long.total).toBeGreaterThan(short.total);
  });

  it("matches embedding heuristic shape", () => {
    expect(estimateEmbeddingTokens("abcd")).toBeGreaterThanOrEqual(1);
    expect(formatTokenCount(15_000)).toBe("~15k");
  });
});
