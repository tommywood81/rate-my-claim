import { describe, expect, it } from "vitest";

import {
  buildSubmitOutcomes,
  processingStatusToStageKey,
  submitActiveStageMessage,
} from "@/lib/research-pipeline-ux";
import type { ClaimDetail } from "@/lib/types";

describe("processingStatusToStageKey", () => {
  it("maps enriching to gathering_evidence", () => {
    expect(processingStatusToStageKey("enriching")).toBe("gathering_evidence");
  });
  it("maps embedding to analyzing", () => {
    expect(processingStatusToStageKey("embedding")).toBe("analyzing");
  });
});

describe("submitActiveStageMessage", () => {
  it("mentions source URLs during enriching", () => {
    const msg = submitActiveStageMessage("enriching", { elapsedSec: 10, sourceUrlCount: 2 });
    expect(msg).toContain("2 linked source");
  });

  it("mentions indexed claims when provided", () => {
    const msg = submitActiveStageMessage("embedding", {
      elapsedSec: 5,
      sourceUrlCount: 0,
      indexedClaims: 28,
    });
    expect(msg).toContain("28");
  });
});

describe("buildSubmitOutcomes", () => {
  it("includes canonical and truth when present", () => {
    const detail = {
      public_slug: "test-claim",
      canonical_claim_text: "Water boils at 100C at sea level",
      processing_status: "awaiting_moderation",
      truth_label: "supported",
      related_slugs: [],
      evidence_count: 0,
    } as ClaimDetail;
    const out = buildSubmitOutcomes(detail, {});
    expect(out.some((o) => o.id === "canonical")).toBe(true);
    expect(out.some((o) => o.id === "truth")).toBe(true);
  });
});
