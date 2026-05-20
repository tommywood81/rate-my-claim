"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { AiAnalysisList } from "@/components/ai-analysis-list";
import { ClaimPipelineStepper } from "@/components/claim-pipeline-stepper";
import { ClaimTimeline } from "@/components/claim-timeline";
import { EvidenceList } from "@/components/evidence-list";
import { apiFetch } from "@/lib/api";
import type { ClaimDetail, ClaimGraph, ClaimTimeline as ClaimTimelineData } from "@/lib/types";

import { ClaimAiAnalysisPanel } from "@/app/claims/[slug]/claim-ai-panel";
import { ClaimGraphSection } from "@/app/claims/[slug]/claim-graph-section";

const TERMINAL = new Set(["completed", "rejected", "failed"]);

/** Still running in Celery (not yet awaiting_moderation). */
const ACTIVE_PIPELINE = new Set([
  "submitted",
  "embedding",
  "duplicate_check",
  "canonicalizing",
  "enriching",
]);

type Props = {
  slug: string;
  initial: ClaimDetail;
  graph: ClaimGraph | null;
  timeline: ClaimTimelineData | null;
};

function pollIntervalMs(status: string | null | undefined): number {
  if (status && ACTIVE_PIPELINE.has(status)) {
    return 2500;
  }
  if (status === "awaiting_moderation") {
    return 8000;
  }
  return 0;
}

export function ClaimPageClient({ slug, initial, graph, timeline }: Props) {
  const [detail, setDetail] = useState(initial);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const detailRef = useRef(detail);
  detailRef.current = detail;

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const next = await apiFetch<ClaimDetail>(`/api/v1/claims/${encodeURIComponent(slug)}`);
      setDetail(next);
      setLastUpdated(new Date());
    } catch {
      /* keep last good state */
    } finally {
      setRefreshing(false);
    }
  }, [slug]);

  useEffect(() => {
    setDetail(initial);
    setLastUpdated(new Date());
  }, [initial]);

  useEffect(() => {
    const proc = initial.processing_status;
    if (proc && ACTIVE_PIPELINE.has(proc)) {
      void refresh();
      const t = setTimeout(() => void refresh(), 1200);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [initial.processing_status, refresh]);

  useEffect(() => {
    const proc = detailRef.current.processing_status;
    const ms = pollIntervalMs(proc);
    if (!proc || TERMINAL.has(proc) || ms === 0) {
      return;
    }
    const id = setInterval(() => {
      void refresh();
    }, ms);
    return () => clearInterval(id);
  }, [detail.processing_status, refresh]);

  const proc = detail.processing_status;
  const inActivePipeline = proc ? ACTIVE_PIPELINE.has(proc) : false;
  const awaitingAi = proc === "awaiting_moderation";
  const processing = proc && !TERMINAL.has(proc);

  const totalEvidence =
    detail.evidence_supporting.length +
    detail.evidence_contradicting.length +
    detail.evidence_contextual.length;

  return (
    <article className="space-y-10">
      <header className="space-y-4 border-b border-[var(--border)] pb-8">
        <p className="owid-kicker">Canonical claim</p>
        <h1 className="owid-page-heading text-3xl sm:text-4xl">{detail.canonical_claim_text}</h1>
        <dl className="owid-stat-grid">
          <div className="owid-stat">
            <dt>Confidence</dt>
            <dd>{detail.confidence_score.toFixed(2)}</dd>
          </div>
          <div className="owid-stat">
            <dt>Controversy</dt>
            <dd>{detail.controversy_score.toFixed(2)}</dd>
          </div>
          <div className="owid-stat">
            <dt>Evidence score</dt>
            <dd>{detail.evidence_score.toFixed(2)}</dd>
          </div>
          <div className="owid-stat">
            <dt>Freshness</dt>
            <dd>{detail.freshness_score.toFixed(2)}</dd>
          </div>
        </dl>
        {detail.aliases.length > 0 && (
          <p className="text-xs text-[var(--muted)]">Also known as: {detail.aliases.join(", ")}</p>
        )}
      </header>

      <section className="owid-panel-live space-y-3" aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-[var(--fg)]">
            {inActivePipeline && (
              <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" />
            )}
            {inActivePipeline
              ? "Research in progress"
              : awaitingAi
                ? "Automated research complete"
                : "Live claim"}
            {detail.visibility_label ? (
              <span className="ml-2 owid-badge">
                {detail.visibility_label}
              </span>
            ) : null}
          </p>
          <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
            {detail.pipeline_stage_label && <span>Stage: {detail.pipeline_stage_label}</span>}
            {refreshing && <span>Updating…</span>}
            {lastUpdated && !refreshing && (
              <span>Updated {lastUpdated.toLocaleTimeString()}</span>
            )}
            <button type="button" className="owid-btn-secondary !min-h-0 px-2 py-1 text-xs" onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
        </div>

        {processing && (
          <>
            <ClaimPipelineStepper currentKey={detail.pipeline_stage_key} pulsing={inActivePipeline} />
            <p className="text-xs text-[var(--muted)]">
              {inActivePipeline
                ? "This page refreshes every few seconds while analysis runs."
                : awaitingAi
                  ? "Background research is done. A moderator may still refine evidence and scores."
                  : "This claim is live; review may continue over time."}
            </p>
          </>
        )}

        {detail.live_ai_summary && (
          <div className="rounded border border-dashed border-[var(--border)] bg-[#faf9f6] p-3 text-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              Research summary
            </p>
            <p className="mt-2 leading-relaxed text-[var(--fg)]">{detail.live_ai_summary}</p>
          </div>
        )}
      </section>

      <section aria-labelledby="evidence-primary-heading" className="owid-panel-evidence space-y-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="evidence-primary-heading" className="owid-section-heading">
            Evidence
          </h2>
          <p className="text-sm text-[var(--muted)]">{totalEvidence} sources on record</p>
        </div>
        <p className="text-sm text-[var(--muted)]">
          Primary material for this claim. URL sources from your submission appear here after moderator review
          syncs citations.
        </p>
        <div className="space-y-8">
          <EvidenceList title="Supporting" items={detail.evidence_supporting} variant="prominent" />
          <EvidenceList title="Contradicting" items={detail.evidence_contradicting} variant="prominent" />
          <EvidenceList title="Contextual" items={detail.evidence_contextual} variant="prominent" />
          {totalEvidence === 0 && (
            <p className="text-sm text-[var(--muted)]">
              {inActivePipeline
                ? "Gathering sources…"
                : "No evidence artifacts on record yet."}
            </p>
          )}
        </div>
      </section>

      {graph && <ClaimGraphSection slug={slug} graph={graph} />}

      <section aria-labelledby="timeline-heading" className="space-y-4">
        <header>
          <h2 id="timeline-heading" className="owid-section-heading">
            History timeline
          </h2>
        </header>
        <ClaimTimeline events={timeline?.events ?? []} />
      </section>

      {detail.related_slugs.length > 0 && (
        <section aria-labelledby="related-heading" className="text-sm">
          <h2 id="related-heading" className="owid-kicker">
            Related claims
          </h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {detail.related_slugs.map((s) => (
              <li key={s}>
                <Link href={`/claims/${s}`} className="owid-chip">
                  {s}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <aside aria-labelledby="ai-panel-heading" className="owid-panel-ai space-y-4">
        <header>
          <h2 id="ai-panel-heading" className="owid-kicker">
            AI-assisted analysis
          </h2>
        </header>
        <AiAnalysisList items={detail.ai_analyses} />
        {detail.ai_analyses.length === 0 && inActivePipeline && (
          <p className="text-xs text-[var(--muted)]">Structured analyses will appear when enrichment finishes.</p>
        )}
        <ClaimAiAnalysisPanel slug={slug} />
      </aside>
    </article>
  );
}
