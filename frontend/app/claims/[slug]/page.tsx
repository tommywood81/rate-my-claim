import type { Metadata } from "next";

import { ClaimAiAnalysisPanel } from "./claim-ai-panel";

type Detail = {
  canonical_claim_text: string;
  public_slug: string;
  confidence_score: number;
  controversy_score: number;
  evidence_score: number;
  freshness_score: number;
  evidence_supporting: { id: string; title: string; summary: string | null; stance: string }[];
  evidence_contradicting: { id: string; title: string; summary: string | null; stance: string }[];
  evidence_contextual: { id: string; title: string; summary: string | null; stance: string }[];
  ai_analyses: { analysis_type: string; model_name: string; generated_text: string; created_at: string }[];
};

export const dynamic = "force-dynamic";

async function load(slug: string) {
  const base = process.env.INTERNAL_API_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${base}/api/v1/claims/${encodeURIComponent(slug)}`, { cache: "no-store" });
  if (!res.ok) return null;
  const body = await res.json();
  return body.data as Detail;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const d = await load(slug);
  if (!d) return { title: "Claim" };
  return {
    title: d.canonical_claim_text.slice(0, 70),
    description: d.canonical_claim_text.slice(0, 160),
    openGraph: { title: d.canonical_claim_text, type: "article" },
  };
}

export default async function ClaimPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const d = await load(slug);
  if (!d) {
    return <p className="text-sm text-[var(--muted)]">Claim not found.</p>;
  }

  return (
    <article className="space-y-8">
      <header className="space-y-2">
        <p className="text-xs uppercase tracking-wide text-[var(--muted)]">Canonical claim</p>
        <h1 className="text-2xl font-semibold leading-snug">{d.canonical_claim_text}</h1>
        <dl className="grid gap-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-[var(--muted)]">Confidence</dt>
            <dd>{d.confidence_score.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Controversy</dt>
            <dd>{d.controversy_score.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Evidence</dt>
            <dd>{d.evidence_score.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Freshness</dt>
            <dd>{d.freshness_score.toFixed(2)}</dd>
          </div>
        </dl>
      </header>

      <section className="space-y-3 rounded border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">Evidence</h2>
        <EvidenceBlock title="Supporting" items={d.evidence_supporting} />
        <EvidenceBlock title="Contradicting" items={d.evidence_contradicting} />
        <EvidenceBlock title="Contextual" items={d.evidence_contextual} />
      </section>

      <section className="space-y-3 rounded border border-dashed border-[var(--border)] bg-[#faf9f6] p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          AI-assisted analysis (non-canonical)
        </h2>
        <ul className="space-y-3 text-sm">
          {d.ai_analyses.map((a, i) => (
            <li key={`${a.analysis_type}-${i}-${a.created_at}`} className="border-l-2 border-[var(--accent)] pl-3">
              <p className="text-xs text-[var(--muted)]">
                {a.analysis_type} · {a.model_name} · {new Date(a.created_at).toLocaleString()}
              </p>
              <p className="mt-1 whitespace-pre-wrap">{a.generated_text}</p>
            </li>
          ))}
          {d.ai_analyses.length === 0 && <li className="text-[var(--muted)]">No AI analyses stored for this claim.</li>}
        </ul>
        <ClaimAiAnalysisPanel slug={slug} />
      </section>
    </article>
  );
}

function EvidenceBlock({
  title,
  items,
}: {
  title: string;
  items: { id: string; title: string; summary: string | null; stance: string }[];
}) {
  if (!items.length) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase text-[var(--muted)]">{title}</h3>
      <ul className="mt-2 space-y-2">
        {items.map((e) => (
          <li key={e.id} className="rounded border border-[var(--border)] bg-white p-3">
            <p className="font-medium">{e.title}</p>
            {e.summary && <p className="mt-1 text-sm text-[var(--muted)]">{e.summary}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
