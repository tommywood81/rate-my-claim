/** Color scales for claim atlas points (0–1 scores). */

export type AtlasColorMode = "confidence" | "controversy" | "evidence";

export function scoreToRgb(mode: AtlasColorMode, value: number): string {
  const t = Math.max(0, Math.min(1, value));
  if (mode === "confidence") {
    const r = Math.round(90 + 70 * (1 - t));
    const g = Math.round(120 + 80 * t);
    const b = Math.round(160 + 60 * t);
    return `rgb(${r},${g},${b})`;
  }
  if (mode === "controversy") {
    const r = Math.round(120 + 120 * t);
    const g = Math.round(140 - 60 * t);
    const b = Math.round(150 - 80 * t);
    return `rgb(${r},${g},${b})`;
  }
  const r = Math.round(100 - 40 * t);
  const g = Math.round(130 + 50 * t);
  const b = Math.round(140 + 30 * t);
  return `rgb(${r},${g},${b})`;
}
