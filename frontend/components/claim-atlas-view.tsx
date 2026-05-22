"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { scoreToRgb, type AtlasColorMode } from "@/lib/claim-atlas-colors";
import type { ClaimAtlasData, ClaimAtlasPoint } from "@/lib/types";

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
    radius: Math.max(3, 5 + scale * 0.02),
  };
}

function scoreForMode(point: ClaimAtlasPoint, mode: AtlasColorMode): number {
  if (mode === "controversy") return point.controversy_score;
  if (mode === "evidence") return point.evidence_score;
  return point.confidence_score;
}

export function ClaimAtlasView() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<ClaimAtlasData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [colorMode, setColorMode] = useState<AtlasColorMode>("confidence");
  const [hovered, setHovered] = useState<ClaimAtlasPoint | null>(null);
  const [selected, setSelected] = useState<ClaimAtlasPoint | null>(null);
  const rotRef = useRef({ x: -0.35, y: 0.55 });
  const zoomRef = useRef(1);
  const dragRef = useRef<{ active: boolean; lastX: number; lastY: number }>({
    active: false,
    lastX: 0,
    lastY: 0,
  });
  const drawRef = useRef<() => void>(() => {});

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
    const dpr = window.devicePixelRatio || 1;
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

    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, "#f8f8f6");
    gradient.addColorStop(1, "#eef3f6");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "rgba(0, 32, 78, 0.08)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w / 2, 24);
    ctx.lineTo(w / 2, h - 24);
    ctx.moveTo(24, h / 2);
    ctx.lineTo(w - 24, h / 2);
    ctx.stroke();

    const projected: { point: ClaimAtlasPoint; screen: ScreenPoint }[] = [];
    for (const point of data.points) {
      let v: Vec3 = { x: point.x, y: point.y, z: point.z };
      v = rotateY(v, rotRef.current.y);
      v = rotateX(v, rotRef.current.x);
      projected.push({ point, screen: projectPoint(v, w, h, zoomRef.current) });
    }
    projected.sort((a, b) => a.screen.depth - b.screen.depth);

    for (const { point, screen } of projected) {
      const color = scoreToRgb(colorMode, scoreForMode(point, colorMode));
      const isHover = hovered?.id === point.id;
      const isSelected = selected?.id === point.id;
      const r = screen.radius * (isHover || isSelected ? 1.45 : 1);
      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.globalAlpha = isHover || isSelected ? 1 : 0.82;
      ctx.arc(screen.sx, screen.sy, r, 0, Math.PI * 2);
      ctx.fill();
      if (isSelected) {
        ctx.strokeStyle = "#00204e";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }, [colorMode, data, hovered, selected]);

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
      zoomRef.current = Math.max(0.4, Math.min(2.5, zoomRef.current - e.deltaY * 0.001));
      drawRef.current();
    };
    container.addEventListener("wheel", onWheel, { passive: false });
    return () => container.removeEventListener("wheel", onWheel);
  }, []);

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
    try {
      (e.target as HTMLCanvasElement).releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  };

  const stats = data
    ? `${data.projected_count} shown · ${data.total_indexed} indexed · ${data.embedding_dimensions}D → 3D (${data.method})`
    : "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="text-sm text-[var(--muted)] max-w-2xl">{data?.note}</p>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-[var(--muted)]" role="status">
            {loading ? "Loading atlas…" : stats}
          </span>
          <button type="button" className="owid-btn-secondary text-sm" onClick={() => void load()} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-800" role="alert">
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
            className={colorMode === key ? "owid-btn-primary text-sm" : "owid-btn-secondary text-sm"}
            onClick={() => setColorMode(key)}
            aria-pressed={colorMode === key}
          >
            {label}
          </button>
        ))}
      </div>

      <div
        ref={containerRef}
        className="owid-card relative h-[min(70vh,520px)] min-h-[360px] w-full overflow-hidden bg-[var(--bg-subtle)]"
        style={{ touchAction: "none" }}
      >
        <canvas
          ref={canvasRef}
          className="h-full w-full cursor-grab touch-none active:cursor-grabbing"
          aria-label="Interactive 3D map of claim embeddings. Drag to rotate, scroll to zoom, click a point to select."
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={() => {
            dragRef.current.active = false;
            setHovered(null);
          }}
        />
        {!loading && data && data.points.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-[var(--muted)]">
            No claims with embeddings yet. Submit claims and wait for enrichment — points will appear here as the
            vector index grows.
          </div>
        )}
        {(hovered || selected) && (
          <div className="pointer-events-none absolute bottom-3 left-3 right-3 sm:right-auto sm:max-w-md">
            <div className="owid-card border-[var(--accent)] bg-white/95 p-3 text-sm shadow-sm">
              <p className="font-medium text-[var(--accent-dark)]">
                {(selected ?? hovered)?.label}
              </p>
              <p className="mt-1 text-xs text-[var(--muted)]">
                Confidence {(selected ?? hovered)!.confidence_score.toFixed(2)} · Controversy{" "}
                {(selected ?? hovered)!.controversy_score.toFixed(2)} · Evidence{" "}
                {(selected ?? hovered)!.evidence_score.toFixed(2)}
              </p>
              {selected && (
                <Link
                  href={`/claims/${selected.public_slug}`}
                  className="pointer-events-auto mt-2 inline-block text-sm font-medium"
                >
                  Open claim →
                </Link>
              )}
            </div>
          </div>
        )}
      </div>

      <p className="text-xs text-[var(--muted)]">
        Drag to rotate · scroll to zoom · click a point to select and open. Nearby points share similar meaning in
        embedding space, not necessarily the same verdict.
      </p>
    </div>
  );
}
