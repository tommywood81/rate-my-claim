import { describe, expect, it } from "vitest";

import {
  atlasPointTruthColor,
  redGreenGradientRgb,
  scoreToRgb,
  truthLabelToRgb,
  TRUTH_ATLAS_COLORS,
} from "@/lib/claim-atlas-colors";

function parseRgb(color: string): [number, number, number] {
  const match = color.match(/^rgb\((\d+),(\d+),(\d+)\)$/);
  expect(match).not.toBeNull();
  return [Number(match![1]), Number(match![2]), Number(match![3])];
}

describe("redGreenGradientRgb", () => {
  it("maps low scores to red and high scores to green", () => {
    const [rLow, gLow] = parseRgb(redGreenGradientRgb(0, "light"));
    const [rHigh, gHigh] = parseRgb(redGreenGradientRgb(1, "light"));
    expect(rLow).toBeGreaterThan(gLow);
    expect(gHigh).toBeGreaterThan(rHigh);
  });
});

describe("scoreToRgb", () => {
  it("uses green-red for confidence and evidence", () => {
    const low = parseRgb(scoreToRgb("confidence", 0, "light"));
    const high = parseRgb(scoreToRgb("confidence", 1, "light"));
    expect(low[0]).toBeGreaterThan(low[1]);
    expect(high[1]).toBeGreaterThan(high[0]);

    const evidenceLow = parseRgb(scoreToRgb("evidence", 0.1, "dark"));
    const evidenceHigh = parseRgb(scoreToRgb("evidence", 0.9, "dark"));
    expect(evidenceLow[0]).toBeGreaterThan(evidenceLow[1]);
    expect(evidenceHigh[1]).toBeGreaterThan(evidenceHigh[0]);
  });

  it("inverts controversy so high controversy is red", () => {
    const calm = parseRgb(scoreToRgb("controversy", 0, "light"));
    const heated = parseRgb(scoreToRgb("controversy", 1, "light"));
    expect(calm[1]).toBeGreaterThan(calm[0]);
    expect(heated[0]).toBeGreaterThan(heated[1]);
  });
});

describe("truthLabelToRgb", () => {
  it("uses green and red for supported and refuted", () => {
    expect(truthLabelToRgb("supported", "light")).toBe(
      TRUTH_ATLAS_COLORS.light.supported,
    );
    expect(truthLabelToRgb("refuted", "dark")).toBe(TRUTH_ATLAS_COLORS.dark.refuted);
    expect(truthLabelToRgb("unknown", "light")).toBe(TRUTH_ATLAS_COLORS.light.unclear);
  });
});

describe("atlasPointTruthColor", () => {
  it("uses solid gray for inconclusive claims", () => {
    const color = atlasPointTruthColor(
      {
        truth_label: "unclear",
      },
      "light",
    );
    expect(color).toBe(TRUTH_ATLAS_COLORS.light.unclear);
  });
});
