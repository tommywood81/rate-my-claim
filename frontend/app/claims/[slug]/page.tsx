import type { Metadata } from "next";
import Link from "next/link";

import { AiAnalysisList } from "@/components/ai-analysis-list";
import { EvidenceList } from "@/components/evidence-list";
import { serverGet } from "@/lib/api-server";
import type { ClaimDetail } from "@/lib/types";

import { ClaimAiAnalysisPanel } from "./claim-ai-panel";

export const dynamic = "force-dynamic";

async function load(slug: string): Promise<ClaimDetail | null> {
  return serverGet<ClaimDetail>(`/api/v1/claims/${encodeURIComponent(slug)}`, { cache: "no-store" });
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
    return (
      <p className="text-sm text-[var(--muted)]" role="status">
        Claim not found.
      </p>
    );
  }

  const totalEvidence =
    d.evidence_supporting.length + d.evidence_contradicting.length + d.evidence_contextual.length;

  return (
    <article className="space-y-10">
      <header className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Canonical claim</p>
        <h1 className="text-2xl font-semibold leading-snug sm:text-3xl">{d.canonical_claim_text}</h1>
        <dl className="grid gap-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-[var(--muted)]">Confidence</dt>
            <dd className="font-medium">{d.confidence_score.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Controversy</dt>
            <dd className="font-medium">{d.controversy_score.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Evidence score</dt>
            <dd className="font-medium">{d.evidence_score.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Freshness</dt>
            <dd className="font-medium">{d.freshness_score.toFixed(2)}</dd>
          </div>
        </dl>
        {d.aliases.length > 0 && (
          <p className="text-xs text-[var(--muted)]">
            Also known as: {d.aliases.join(", ")}
          </p>
        )}
      </header>

      <section
        aria-labelledby="evidence-primary-heading"
        className="space-y-6 rounded-lg border-2 border-[var(--accent)]/20 bg-[var(--card)] p-5 shadow-sm sm:p-6"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="evidence-primary-heading" className="text-lg font-semibold text-[var(--fg)]">
            Evidence
          </h2>
          <p className="text-sm text-[var(--muted)]">{totalEvidence} sources on record</p>
        </div>
        <p className="text-sm text-[var(--muted)]">
          Primary material for this claim. Review sources, publishers, and retrieval dates before any AI summary.
        </p>
        <div className="space-y-8">
          <EvidenceList title="Supporting" items={d.evidence_supporting} variant="prominent" />
          <EvidenceList title="Contradicting" items={d.evidence_contradicting} variant="prominent" />
          <EvidenceList title="Contextual" items={d.evidence_contextual} variant="prominent" />
          {totalEvidence === 0 && (
            <p className="text-sm text-[var(--muted)]">No evidence artifacts linked yet.</p>
          )}
        </div>
      </section>

      {d.related_slugs.length > 0 && (
        <section aria-labelledby="related-heading" className="text-sm">
          <h2 id="related-heading" className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            Related claims
          </h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {d.related_slugs.map((s) => (
              <li key={s}>
                <Link
                  href={`/claims/${s}`}
                  className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-[var(--accent)] hover:underline"
                >
                  {s}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <aside
        aria-labelledby="ai-panel-heading"
        className="space-y-4 rounded-lg border border-dashed border-[var(--border)] bg-[#faf9f6] p-5"
      >
        <header>
          <h2 id="ai-panel-heading" className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
            AI-assisted analysis
          </h2>
          <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
            Non-canonical summaries. Each entry shows provider, model, and generation time. Do not treat as primary
            evidence.
          </p>
        </header>
        <AiAnalysisList items={d.ai_analyses} />
        <ClaimAiAnalysisPanel slug={slug} />
      </aside>
    </article>
  );
}
