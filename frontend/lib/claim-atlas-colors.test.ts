import { describe, expect, it } from "vitest";

import { scoreToRgb } from "@/lib/claim-atlas-colors";

describe("scoreToRgb", () => {
  it("returns distinct colors for low and high confidence", () => {
    const low = scoreToRgb("confidence", 0);
    const high = scoreToRgb("confidence", 1);
    expect(low).not.toBe(high);
    expect(low).toMatch(/^rgb\(/);
  });
});
