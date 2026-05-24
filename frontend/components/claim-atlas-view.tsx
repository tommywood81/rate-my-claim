"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import type { AtlasColorMode } from "@/lib/claim-atlas-colors";
import {
  ATLAS_STORAGE_THEME,
  getAtlasPalette,
  paintAtlasBackdrop,
  paintAtlasPoint,
  scoreToThemeRgb,
  type AtlasVisualTheme,
} from "@/lib/claim-atlas-theme";
import type { ClaimAtlasData, ClaimAtlasPoint } from "@/lib/types";

const IDLE_MS = 5000;
const AUTO_ROTATE_Y = 0.0022;
const AUTO_ROTATE_X = 0.0006;

type Vec3 = { x: number; y: number; z: number };
type ScreenPoint = { sx: number; sy: number; depth: number; radius: number };

function rotateY(p: Vec3, angle: number): Vec3 {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  return { x: p.x * c + p.z * s, y: p.y, z: -p.x * s + p.z * c };
}

function rotateX(p: Vec3, angle: number): Vec3 {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  return { x: p.x, y: p.y * c - p.z * s, z: p.y * s + p.z * c };
}

function projectPoint(p: Vec3, width: number, height: number, zoom: number): ScreenPoint {
  const perspective = 2.2;
  const scale = (zoom * Math.min(width, height) * 0.22) / (perspective + p.z);
  return {
    sx: width / 2 + p.x * scale,
    sy: height / 2 - p.y * scale,
    depth: p.z,
    radius: Math.max(3.5, 5.5 + scale * 0.022),
  };
}

function scoreForMode(point: ClaimAtlasPoint, mode: AtlasColorMode): number {
  if (mode === "controversy") return point.controversy_score;
  if (mode === "evidence") return point.evidence_score;
  return point.confidence_score;
}

function readStoredTheme(): AtlasVisualTheme {
  if (typeof window === "undefined") return "dark";
  try {
    const v = localStorage.getItem(ATLAS_STORAGE_THEME);
    return v === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function ClaimAtlasView() {
  const rootRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<ClaimAtlasData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [colorMode, setColorMode] = useState<AtlasColorMode>("confidence");
  const [visualTheme, setVisualTheme] = useState<AtlasVisualTheme>("dark");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [hovered, setHovered] = useState<ClaimAtlasPoint | null>(null);
  const [selected, setSelected] = useState<ClaimAtlasPoint | null>(null);
  const [reduceMotion, setReduceMotion] = useState(false);
  const rotRef = useRef({ x: -0.35, y: 0.55 });
  const zoomRef = useRef(1);
  const lastInteractRef = useRef(Date.now());
  const dragRef = useRef<{ active: boolean; lastX: number; lastY: number }>({
    active: false,
    lastX: 0,
    lastY: 0,
  });
  const drawRef = useRef<() => void>(() => {});

  useEffect(() => {
    setVisualTheme(readStoredTheme());
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduceMotion(mq.matches);
    const onChange = () => setReduceMotion(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const markInteract = useCallback(() => {
    lastInteractRef.current = Date.now();
  }, []);

  const setTheme = useCallback((theme: AtlasVisualTheme) => {
    setVisualTheme(theme);
    try {
      localStorage.setItem(ATLAS_STORAGE_THEME, theme);
    } catch {
      /* private mode */
    }
    markInteract();
  }, [markInteract]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/atlas/claims", { cache: "no-store" });
      if (!res.ok) throw new Error("Could not load embedding atlas");
      const body = (await res.json()) as { data: ClaimAtlasData; meta?: { truncated?: boolean } };
      setData(body.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || !data) return;

    const rect = container.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    const w = Math.max(320, Math.floor(rect.width));
    const h = Math.max(360, Math.floor(rect.height));
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const palette = getAtlasPalette(visualTheme);
    const isDark = visualTheme === "dark";
    paintAtlasBackdrop(ctx, w, h, palette, visualTheme);

    const projected: { point: ClaimAtlasPoint; screen: ScreenPoint }[] = [];
    for (const point of data.points) {
      let v: Vec3 = { x: point.x, y: point.y, z: point.z };
      v = rotateY(v, rotRef.current.y);
      v = rotateX(v, rotRef.current.x);
      projected.push({ point, screen: projectPoint(v, w, h, zoomRef.current) });
    }
    projected.sort((a, b) => a.screen.depth - b.screen.depth);

    for (const { point, screen } of projected) {
      const color = scoreToThemeRgb(colorMode, scoreForMode(point, colorMode), visualTheme);
      const isHover = hovered?.id === point.id;
      const isSelected = selected?.id === point.id;
      const r = screen.radius * (isHover || isSelected ? 1.4 : 1);
      paintAtlasPoint(ctx, screen.sx, screen.sy, r, color, palette, {
        hover: isHover,
        selected: isSelected,
        dark: isDark,
      });
    }
  }, [colorMode, data, hovered, selected, visualTheme]);

  drawRef.current = draw;

  useEffect(() => {
    draw();
  }, [draw]);

  useEffect(() => {
    const onResize = () => drawRef.current();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      markInteract();
      zoomRef.current = Math.max(0.4, Math.min(2.5, zoomRef.current - e.deltaY * 0.001));
      drawRef.current();
    };
    container.addEventListener("wheel", onWheel, { passive: false });
    return () => container.removeEventListener("wheel", onWheel);
  }, [markInteract]);

  useEffect(() => {
    if (reduceMotion || !data?.points.length) return;
    let raf = 0;
    const tick = () => {
      const idle = Date.now() - lastInteractRef.current >= IDLE_MS;
      if (idle && !dragRef.current.active) {
        rotRef.current.y += AUTO_ROTATE_Y;
        rotRef.current.x += AUTO_ROTATE_X;
        drawRef.current();
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [data, reduceMotion]);

  useEffect(() => {
    const onFs = () => setIsFullscreen(document.fullscreenElement === rootRef.current);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const toggleFullscreen = useCallback(async () => {
    const el = rootRef.current;
    if (!el) return;
    markInteract();
    try {
      if (document.fullscreenElement === el) {
        await document.exitFullscreen();
      } else {
        await el.requestFullscreen();
      }
    } catch {
      /* unsupported */
    }
  }, [markInteract]);

  const pickPoint = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      if (!canvas || !data) return null;
      const rect = canvas.getBoundingClientRect();
      const x = clientX - rect.left;
      const y = clientY - rect.top;
      const w = rect.width;
      const h = rect.height;
      let best: { point: ClaimAtlasPoint; dist: number } | null = null;
      for (const point of data.points) {
        let v: Vec3 = { x: point.x, y: point.y, z: point.z };
        v = rotateY(v, rotRef.current.y);
        v = rotateX(v, rotRef.current.x);
        const screen = projectPoint(v, w, h, zoomRef.current);
        const dx = screen.sx - x;
        const dy = screen.sy - y;
        const dist = Math.hypot(dx, dy);
        const hit = screen.radius + 6;
        if (dist <= hit && (!best || dist < best.dist)) {
          best = { point, dist };
        }
      }
      return best?.point ?? null;
    },
    [data],
  );

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    markInteract();
    const hit = pickPoint(e.clientX, e.clientY);
    if (hit) {
      setSelected(hit);
      setHovered(hit);
      return;
    }
    dragRef.current = { active: true, lastX: e.clientX, lastY: e.clientY };
    (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (dragRef.current.active) {
      markInteract();
      const dx = e.clientX - dragRef.current.lastX;
      const dy = e.clientY - dragRef.current.lastY;
      dragRef.current.lastX = e.clientX;
      dragRef.current.lastY = e.clientY;
      rotRef.current.y += dx * 0.008;
      rotRef.current.x += dy * 0.008;
      draw();
      return;
    }
    setHovered(pickPoint(e.clientX, e.clientY));
  };

  const onPointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    dragRef.current.active = false;
    markInteract();
    try {
      (e.target as HTMLCanvasElement).releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  };

  const stats = data
    ? `${data.projected_count} shown · ${data.total_indexed} indexed · ${data.embedding_dimensions}D → 3D (${data.method})`
    : "";

  const palette = getAtlasPalette(visualTheme);
  const isDark = visualTheme === "dark";
  const focus = selected ?? hovered;
  const toolBtn =
    "rounded border border-sky-500/35 bg-[rgba(8,18,36,0.88)] px-3 py-1.5 text-sm text-slate-200 hover:border-sky-300/60 hover:bg-[rgba(12,28,52,0.95)] disabled:opacity-50";
  const toolBtnActive =
    "rounded border border-sky-300/75 bg-sky-900/50 px-3 py-1.5 text-sm text-slate-100";

  return (
    <div
      ref={rootRef}
      className={
        isFullscreen
          ? "fixed inset-0 z-50 flex flex-col overflow-auto p-4 sm:p-6"
          : "space-y-4"
      }
      style={
        isFullscreen
          ? { background: isDark ? "#040810" : "#f8f8f6", color: isDark ? "#e2e8f0" : undefined }
          : undefined
      }
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p
          className="text-sm max-w-2xl"
          style={{ color: isFullscreen && isDark ? palette.panelMuted : undefined }}
        >
          <span className={isFullscreen ? "" : "text-[var(--muted)]"}>{data?.note}</span>
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="text-xs"
            role="status"
            style={{ color: isFullscreen && isDark ? palette.panelMuted : undefined }}
          >
            <span className={isFullscreen ? "" : "text-[var(--muted)]"}>
              {loading ? "Loading atlas…" : stats}
            </span>
          </span>
          <button
            type="button"
            className={isDark ? toolBtn : "owid-btn-secondary text-sm"}
            onClick={() => setTheme(isDark ? "light" : "dark")}
            aria-pressed={isDark}
            title={isDark ? "Switch to light background" : "Switch to dark lab view"}
          >
            {isDark ? "Light mode" : "Dark mode"}
          </button>
          <button
            type="button"
            className={isDark ? toolBtn : "owid-btn-secondary text-sm"}
            onClick={() => void toggleFullscreen()}
            aria-pressed={isFullscreen}
          >
            {isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          </button>
          <button
            type="button"
            className={isDark ? toolBtn : "owid-btn-secondary text-sm"}
            onClick={() => void load()}
            disabled={loading}
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-400" role="alert">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2" role="group" aria-label="Color points by">
        {(
          [
            ["confidence", "Confidence"],
            ["controversy", "Controversy"],
            ["evidence", "Evidence score"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={
              colorMode === key
                ? isDark
                  ? toolBtnActive
                  : "owid-btn-primary text-sm"
                : isDark
                  ? toolBtn
                  : "owid-btn-secondary text-sm"
            }
            onClick={() => {
              setColorMode(key);
              markInteract();
            }}
            aria-pressed={colorMode === key}
          >
            {label}
          </button>
        ))}
      </div>

      <div
        ref={containerRef}
        className={
          isFullscreen
            ? "relative min-h-0 flex-1 w-full overflow-hidden rounded-lg border"
            : "owid-card relative h-[min(70vh,520px)] min-h-[360px] w-full overflow-hidden"
        }
        style={{
          touchAction: "none",
          borderColor: isDark ? "rgba(56, 189, 248, 0.2)" : undefined,
          background: isDark ? "#060d18" : undefined,
        }}
      >
        <canvas
          ref={canvasRef}
          className="h-full w-full cursor-grab touch-none active:cursor-grabbing"
          aria-label="Interactive 3D map of claim embeddings. Drag to rotate, scroll to zoom, click a point to select. Auto-rotates after five seconds idle."
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={() => {
            dragRef.current.active = false;
            setHovered(null);
          }}
        />
        {!loading && data && data.points.length === 0 && (
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center p-6 text-center text-sm"
            style={{ color: palette.hint }}
          >
            No claims on the map yet. Submit one — dots appear as the library grows.
          </div>
        )}
        {focus && (
          <div className="pointer-events-none absolute bottom-3 left-3 right-3 sm:right-auto sm:max-w-md">
            <div
              className="rounded-lg border p-3 text-sm shadow-lg backdrop-blur-sm"
              style={{
                background: palette.panelBg,
                borderColor: palette.panelBorder,
                color: palette.panelText,
              }}
            >
              <p className="font-medium">{focus.label}</p>
              <p className="mt-1 text-xs" style={{ color: palette.panelMuted }}>
                Confidence {focus.confidence_score.toFixed(2)} · Controversy{" "}
                {focus.controversy_score.toFixed(2)} · Evidence {focus.evidence_score.toFixed(2)}
              </p>
              {selected && (
                <Link
                  href={`/claims/${selected.public_slug}`}
                  className="pointer-events-auto mt-2 inline-block text-sm font-medium"
                  style={{ color: isDark ? "#7dd3fc" : "var(--accent-dark)" }}
                >
                  Open claim →
                </Link>
              )}
            </div>
          </div>
        )}
        {isDark && !reduceMotion && (
          <p
            className="pointer-events-none absolute right-3 top-3 text-[10px] uppercase tracking-wider"
            style={{ color: palette.panelMuted }}
          >
            Auto-rotate when idle
          </p>
        )}
      </div>

      {!isFullscreen && (
        <p className="text-xs text-[var(--muted)]">
          Drag to rotate · scroll to zoom · click a point to select. After 5s without input the view slowly spins.
          Similar wording clusters together — truth status can still differ. Open a dot for the full living record.
        </p>
      )}
    </div>
  );
}
