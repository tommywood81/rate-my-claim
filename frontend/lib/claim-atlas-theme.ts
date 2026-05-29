/** Visual theme for the embedding atlas canvas (lab / light). */

import {
  scoreToThemeRgb as scoreToAtlasRgb,
  type AtlasColorMode,
  type AtlasVisualTheme,
} from "@/lib/claim-atlas-colors";

export type { AtlasVisualTheme } from "@/lib/claim-atlas-colors";

export type AtlasPalette = {
  bgTop: string;
  bgBottom: string;
  vignette: string;
  gridMajor: string;
  gridMinor: string;
  axis: string;
  star: string;
  hint: string;
  panelBg: string;
  panelBorder: string;
  panelText: string;
  panelMuted: string;
  selectedRing: string;
  hoverRing: string;
};

export const ATLAS_STORAGE_THEME = "rmc-atlas-theme";

export function getAtlasPalette(theme: AtlasVisualTheme): AtlasPalette {
  if (theme === "dark") {
    return {
      bgTop: "#0c1830",
      bgBottom: "#040810",
      vignette: "rgba(0, 0, 0, 0.55)",
      gridMajor: "rgba(56, 189, 248, 0.12)",
      gridMinor: "rgba(56, 189, 248, 0.05)",
      axis: "rgba(125, 211, 252, 0.35)",
      star: "rgba(148, 163, 184, 0.35)",
      hint: "rgba(148, 163, 184, 0.85)",
      panelBg: "rgba(8, 18, 36, 0.92)",
      panelBorder: "rgba(56, 189, 248, 0.45)",
      panelText: "#e2e8f0",
      panelMuted: "#94a3b8",
      selectedRing: "#f8fafc",
      hoverRing: "rgba(125, 211, 252, 0.9)",
    };
  }
  return {
    bgTop: "#f8f8f6",
    bgBottom: "#e8f0f6",
    vignette: "rgba(255, 255, 255, 0)",
    gridMajor: "rgba(0, 32, 78, 0.1)",
    gridMinor: "rgba(0, 32, 78, 0.05)",
    axis: "rgba(19, 103, 150, 0.25)",
    star: "rgba(0, 32, 78, 0.06)",
    hint: "rgba(92, 90, 84, 0.9)",
    panelBg: "rgba(255, 255, 255, 0.95)",
    panelBorder: "rgba(19, 103, 150, 0.35)",
    panelText: "#2a2925",
    panelMuted: "#5c5a54",
    selectedRing: "#00204e",
    hoverRing: "rgba(19, 103, 150, 0.85)",
  };
}

export function scoreToThemeRgb(
  mode: Exclude<AtlasColorMode, "truth">,
  value: number,
  theme: AtlasVisualTheme,
): string {
  return scoreToAtlasRgb(mode, value, theme);
}

/** Deterministic starfield for lab backdrop. */
function starAt(i: number, w: number, h: number): { x: number; y: number; a: number } {
  const s = Math.sin(i * 127.1 + w * 0.017) * 43758.5453;
  const t = s - Math.floor(s);
  const u = Math.sin(i * 269.5 + h * 0.013) * 12345.6789;
  const v = u - Math.floor(u);
  return { x: t * w, y: v * h, a: 0.25 + (t * 0.75) % 1 * 0.55 };
}

export function paintAtlasBackdrop(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  palette: AtlasPalette,
  theme: AtlasVisualTheme,
): void {
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, palette.bgTop);
  grad.addColorStop(1, palette.bgBottom);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  if (theme === "dark") {
    const count = Math.min(120, Math.floor((w * h) / 12000));
    for (let i = 0; i < count; i++) {
      const { x, y, a } = starAt(i, w, h);
      ctx.fillStyle = palette.star;
      ctx.globalAlpha = a;
      ctx.beginPath();
      ctx.arc(x, y, i % 3 === 0 ? 1.2 : 0.6, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  const cx = w / 2;
  const cy = h / 2;
  for (let ring = 1; ring <= 4; ring++) {
    const radius = (ring / 4) * Math.min(w, h) * 0.46;
    ctx.strokeStyle = ring % 2 === 0 ? palette.gridMajor : palette.gridMinor;
    ctx.lineWidth = ring === 4 ? 1 : 0.5;
    ctx.beginPath();
    ctx.ellipse(cx, cy, radius, radius * 0.42, 0, 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.strokeStyle = palette.axis;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx, 28);
  ctx.lineTo(cx, h - 28);
  ctx.moveTo(28, cy);
  ctx.lineTo(w - 28, cy);
  ctx.stroke();

  const vig = ctx.createRadialGradient(cx, cy, Math.min(w, h) * 0.15, cx, cy, Math.min(w, h) * 0.72);
  vig.addColorStop(0, "rgba(0,0,0,0)");
  vig.addColorStop(1, palette.vignette);
  ctx.fillStyle = vig;
  ctx.fillRect(0, 0, w, h);
}

export function paintAtlasPoint(
  ctx: CanvasRenderingContext2D,
  sx: number,
  sy: number,
  r: number,
  fill: string,
  palette: AtlasPalette,
  opts: { hover: boolean; selected: boolean; dark: boolean },
): void {
  if (opts.dark) {
    ctx.shadowColor = fill;
    ctx.shadowBlur = opts.hover || opts.selected ? 16 : 8;
  } else {
    ctx.shadowBlur = 0;
  }

  ctx.beginPath();
  ctx.fillStyle = fill;
  ctx.globalAlpha = opts.hover || opts.selected ? 1 : 0.88;
  ctx.arc(sx, sy, r, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.globalAlpha = 1;

  if (opts.selected || opts.hover) {
    ctx.beginPath();
    ctx.strokeStyle = opts.selected ? palette.selectedRing : palette.hoverRing;
    ctx.lineWidth = opts.selected ? 2 : 1.5;
    ctx.arc(sx, sy, r + 3, 0, Math.PI * 2);
    ctx.stroke();
  }

  if (opts.dark) {
    ctx.beginPath();
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.arc(sx - r * 0.25, sy - r * 0.25, Math.max(1, r * 0.35), 0, Math.PI * 2);
    ctx.fill();
  }
}
