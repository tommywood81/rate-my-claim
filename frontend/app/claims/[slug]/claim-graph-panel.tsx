"use client";

import {
  Background,
  Controls,
  type Edge,
  type Node,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { ClaimGraph } from "@/lib/types";

const FILTER_GROUPS: { label: string; types: string[] }[] = [
  { label: "Contradictions", types: ["contradiction"] },
  { label: "Dependencies", types: ["dependency"] },
  { label: "Refinements", types: ["refinement"] },
  { label: "Causal", types: ["causal_link"] },
  { label: "Context", types: ["contextual_relationship", "duplicate"] },
];

function toFlowGraph(graph: ClaimGraph): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = graph.nodes.map((n) => ({
    id: n.id,
    type: n.type,
    position: n.position,
    data: n.data,
    draggable: true,
    selectable: true,
  }));
  const edges: Edge[] = graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label ?? undefined,
    type: "default",
    animated: false,
    data: e.data,
    style: edgeStyle(e.data?.relationship_type ?? e.label ?? ""),
  }));
  return { nodes, edges };
}

function edgeStyle(relType: string): React.CSSProperties {
  const t = relType.toLowerCase();
  if (t.includes("contradiction")) return { stroke: "#b45309" };
  if (t.includes("dependency")) return { stroke: "#1e3a5f" };
  if (t.includes("refinement")) return { stroke: "#047857" };
  if (t.includes("causal")) return { stroke: "#6d28d9" };
  if (t.includes("evidence")) return { stroke: "#6b7280", strokeDasharray: "4 4" };
  return { stroke: "#9ca3af" };
}

function ClaimNode({ data }: { data: Record<string, unknown> }) {
  const label = String(data.label ?? "");
  const slug = data.slug as string | null;
  const isFocus = Boolean(data.is_focus);
  const confidence = data.confidence_score as number | undefined;
  return (
    <div
      className={`max-w-[200px] rounded border bg-white px-3 py-2 text-xs shadow-sm ${
        isFocus ? "border-[var(--accent)] ring-2 ring-[var(--accent)]/20" : "border-[var(--border)]"
      }`}
    >
      {slug ? (
        <Link href={`/claims/${slug}`} className="font-medium leading-snug text-[var(--fg)] hover:underline">
          {label}
        </Link>
      ) : (
        <p className="font-medium leading-snug">{label}</p>
      )}
      {confidence != null && (
        <p className="mt-1 text-[var(--muted)]" title="Assessment confidence">
          assess {confidence.toFixed(2)}
        </p>
      )}
    </div>
  );
}

function EvidenceClusterNode({ data }: { data: Record<string, unknown> }) {
  const label = String(data.label ?? "Evidence");
  const count = data.count as number | undefined;
  const stance = String(data.stance ?? "");
  const border =
    stance === "contradicts"
      ? "border-amber-600"
      : stance === "supports"
        ? "border-emerald-700"
        : "border-slate-500";
  return (
    <div className={`rounded-lg border-2 ${border} bg-[#faf9f6] px-3 py-2 text-xs`}>
      <p className="font-semibold">{label}</p>
      {count != null && <p className="text-[var(--muted)]">{count} sources</p>}
    </div>
  );
}

const nodeTypes = { claim: ClaimNode, evidence_cluster: EvidenceClusterNode };

export function ClaimGraphPanel({ slug, initialGraph }: { slug: string; initialGraph: ClaimGraph }) {
  const [activeTypes, setActiveTypes] = useState<string[]>([]);
  const [graphMeta, setGraphMeta] = useState({ truncated: initialGraph.truncated });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initial = useMemo(() => toFlowGraph(initialGraph), [initialGraph]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  const loadGraph = useCallback(
    async (types: string[]) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ depth: "1", include_evidence_clusters: "true" });
        if (types.length) params.set("types", types.join(","));
        const res = await fetch(`/api/v1/claims/${encodeURIComponent(slug)}/graph?${params}`);
        if (!res.ok) throw new Error("Failed to load graph");
        const body = (await res.json()) as { data: ClaimGraph };
        const flow = toFlowGraph(body.data);
        setNodes(flow.nodes);
        setEdges(flow.edges);
        setGraphMeta({ truncated: body.data.truncated });
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Graph load failed");
      } finally {
        setLoading(false);
      }
    },
    [slug, setNodes, setEdges],
  );

  const [filtersTouched, setFiltersTouched] = useState(false);

  useEffect(() => {
    if (!filtersTouched) return;
    void loadGraph(activeTypes);
  }, [activeTypes, filtersTouched, loadGraph]);

  function toggleGroup(types: string[]) {
    setFiltersTouched(true);
    const allActive = types.every((t) => activeTypes.includes(t));
    if (allActive) {
      setActiveTypes((prev) => prev.filter((t) => !types.includes(t)));
    } else {
      setActiveTypes((prev) => [...new Set([...prev, ...types])]);
    }
  }

  function showAllTypes() {
    setFiltersTouched(true);
    setActiveTypes([]);
  }

  const prefersReducedMotion =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return (
    <section aria-labelledby="graph-heading" className="owid-card-padded space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="graph-heading" className="owid-section-heading">
            How this claim connects to others
          </h2>
          <p className="text-xs text-[var(--muted)]">
            Connections, contradictions, and clusters — how this claim relates to others in the library. Drag
            nodes; zoom with the controls.
          </p>
        </div>
        {graphMeta.truncated && (
          <span className="text-xs text-amber-800">Graph truncated for performance</span>
        )}
      </header>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter relationship types">
        {FILTER_GROUPS.map((g) => {
          const active = g.types.every((t) => activeTypes.includes(t));
          return (
            <button
              key={g.label}
              type="button"
              aria-pressed={active}
              onClick={() => toggleGroup(g.types)}
              className={`owid-chip text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] ${
                active ? "owid-chip-active" : ""
              }`}
            >
              {g.label}
            </button>
          );
        })}
        <button
          type="button"
          className="owid-chip text-xs"
          onClick={showAllTypes}
        >
          All types
        </button>
      </div>

      {error && <p className="text-xs text-red-700">{error}</p>}
      {loading && <p className="text-xs text-[var(--muted)]">Updating graph…</p>}

      <div className="h-[420px] overflow-hidden border border-[var(--border)] bg-white">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          maxZoom={1.8}
          nodesDraggable
          elementsSelectable
          onlyRenderVisibleElements
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{ animated: !prefersReducedMotion }}
        >
          <Background gap={16} color="#e8e6e1" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </section>
  );
}
