/** Color scales for claim atlas points (0–1 scores and truth status). */

export type AtlasVisualTheme = "dark" | "light";

export type AtlasColorMode = "truth" | "confidence" | "controversy" | "evidence";

export type TruthLabel = "supported" | "refuted" | "unclear";

export const TRUTH_ATLAS_COLORS: Record<
  AtlasVisualTheme,
  Record<TruthLabel, string>
> = {
  light: {
    supported: "#15803d",
    refuted: "#b91c1c",
    unclear: "#64748b",
  },
  dark: {
    supported: "#4ade80",
    refuted: "#f87171",
    unclear: "#94a3b8",
  },
};

export const TRUTH_ATLAS_LEGEND: { key: TruthLabel; label: string }[] = [
  { key: "supported", label: "Supported" },
  { key: "refuted", label: "Refuted" },
  { key: "unclear", label: "Inconclusive" },
];

/** Interpolate red (low) → green (high). */
export function redGreenGradientRgb(value: number, theme: AtlasVisualTheme): string {
  const t = Math.max(0, Math.min(1, value));
  if (theme === "dark") {
    const r = Math.round(248 - 189 * t);
    const g = Math.round(113 + 115 * t);
    const b = Math.round(113 - 55 * t);
    return `rgb(${r},${g},${b})`;
  }
  const r = Math.round(220 - 155 * t);
  const g = Math.round(38 + 120 * t);
  const b = Math.round(38 + 10 * t);
  return `rgb(${r},${g},${b})`;
}

export function normalizeTruthLabel(label: string | null | undefined): TruthLabel {
  if (label === "supported" || label === "refuted") return label;
  return "unclear";
}

export function truthLabelToRgb(
  label: string | null | undefined,
  theme: AtlasVisualTheme,
): string {
  return TRUTH_ATLAS_COLORS[theme][normalizeTruthLabel(label)];
}

export function formatTruthLabelDisplay(label: string | null | undefined): string {
  const key = normalizeTruthLabel(label);
  return TRUTH_ATLAS_LEGEND.find((item) => item.key === key)?.label ?? "Inconclusive";
}

export function scoreToRgb(
  mode: Exclude<AtlasColorMode, "truth">,
  value: number,
  theme: AtlasVisualTheme = "light",
): string {
  if (mode === "controversy") {
    return redGreenGradientRgb(1 - value, theme);
  }
  return redGreenGradientRgb(value, theme);
}

export function scoreToThemeRgb(
  mode: Exclude<AtlasColorMode, "truth">,
  value: number,
  theme: AtlasVisualTheme,
): string {
  return scoreToRgb(mode, value, theme);
}

/** Truth verdict colors for supported, refuted, and inconclusive claims. */
export function atlasPointTruthColor(
  point: { truth_label?: string | null },
  theme: AtlasVisualTheme,
): string {
  return truthLabelToRgb(point.truth_label, theme);
}

export function atlasPointColor(
  point: {
    truth_label?: string | null;
    confidence_score: number;
    controversy_score: number;
    evidence_score: number;
  },
  mode: AtlasColorMode,
  theme: AtlasVisualTheme,
): string {
  if (mode === "truth") return atlasPointTruthColor(point, theme);
  const score =
    mode === "controversy"
      ? point.controversy_score
      : mode === "evidence"
        ? point.evidence_score
        : point.confidence_score;
  return scoreToThemeRgb(mode, score, theme);
}
