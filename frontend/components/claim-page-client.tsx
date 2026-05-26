"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { AiAnalysisList } from "@/components/ai-analysis-list";
import { ClaimPipelineStepper } from "@/components/claim-pipeline-stepper";
import { ClaimTimeline } from "@/components/claim-timeline";
import { EvidenceList } from "@/components/evidence-list";
import { ClaimTruthBanner } from "@/components/claim-truth-banner";
import { ResearchPipelineProgress } from "@/components/research-pipeline-progress";
import { apiFetch } from "@/lib/api";
import { claimPollingHint, isAssessmentComplete } from "@/lib/research-pipeline-ux";
import type { ClaimDetail, ClaimGraph, ClaimTimeline as ClaimTimelineData } from "@/lib/types";

import { ClaimGraphSection } from "@/app/claims/[slug]/claim-graph-section";
import { ClaimStaffAiTools } from "@/components/claim-staff-ai-tools";
import { formatLastAiRun } from "@/lib/claim-ai-moderation";

const TERMINAL = new Set(["completed", "awaiting_moderation", "rejected", "failed", "revision_requested"]);

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
  justSubmitted?: boolean;
};

function pollIntervalMs(status: string | null | undefined): number {
  if (status && ACTIVE_PIPELINE.has(status)) {
    return 2500;
  }
  return 0;
}

export function ClaimPageClient({ slug, initial, graph, timeline, justSubmitted = false }: Props) {
  const [detail, setDetail] = useState(initial);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [pageElapsedSec, setPageElapsedSec] = useState(0);
  const [showSubmittedBanner, setShowSubmittedBanner] = useState(justSubmitted);
  const pageStartedAt = useRef(Date.now());
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
    if (justSubmitted) return;
    try {
      const flagged = sessionStorage.getItem("rmc_just_submitted_slug");
      if (flagged === slug) {
        setShowSubmittedBanner(true);
        sessionStorage.removeItem("rmc_just_submitted_slug");
      }
    } catch {
      /* ignore */
    }
  }, [slug, justSubmitted]);

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

  useEffect(() => {
    const proc = detail.processing_status;
    const stillRunning = proc && ACTIVE_PIPELINE.has(proc);
    if (!stillRunning) return;
    const id = setInterval(() => {
      setPageElapsedSec(Math.floor((Date.now() - pageStartedAt.current) / 1000));
    }, 500);
    return () => clearInterval(id);
  }, [detail.processing_status]);

  useEffect(() => {
    if (!showSubmittedBanner) return;
    const id = setTimeout(() => setShowSubmittedBanner(false), 12000);
    return () => clearTimeout(id);
  }, [showSubmittedBanner]);

  const proc = detail.processing_status;
  const inActivePipeline = proc ? ACTIVE_PIPELINE.has(proc) : false;
  const assessmentDone = isAssessmentComplete(detail);
  const processing = proc && ACTIVE_PIPELINE.has(proc);
  const pollingHint = claimPollingHint(pageElapsedSec, proc);

  const totalEvidence =
    detail.evidence_supporting.length +
    detail.evidence_contradicting.length +
    detail.evidence_contextual.length;

  return (
    <article className="space-y-10">
      <header className="space-y-4 border-b border-[var(--border)] pb-8">
        <p className="owid-kicker">Living record</p>
        <h1 className="owid-page-heading text-3xl sm:text-4xl">{detail.canonical_claim_text}</h1>
        <dl className="owid-stat-grid">
          <div className="owid-stat">
            <dt title="How confident the current assessment is — not the probability the claim is true">
              Assessment confidence
            </dt>
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

      {detail.truth_label && (
        <ClaimTruthBanner label={detail.truth_label} />
      )}

      {showSubmittedBanner && (
        <p className="owid-card border-l-4 border-l-[var(--accent)] px-4 py-3 text-sm text-[var(--fg)]">
          Your claim is <strong>live</strong> — one page, one record. We&apos;re gathering sources and
          counterpoints; truth status and scores update here as the assessment runs.
        </p>
      )}

      <section className="owid-panel-live space-y-4" aria-live="polite">
        {(processing || showSubmittedBanner) && (
          <ResearchPipelineProgress
            processingStatus={proc ?? "submitted"}
            elapsedSec={inActivePipeline ? pageElapsedSec : undefined}
            pollingHint={pollingHint}
          />
        )}

        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-[var(--fg)]">
            {inActivePipeline && (
              <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" />
            )}
            {inActivePipeline
              ? "Assessing…"
              : assessmentDone
                ? "Live — assessment complete"
                : "Live record"}
            {detail.visibility_label ? (
              <span className="ml-2 owid-badge">
                {detail.visibility_label}
              </span>
            ) : null}
          </p>
          <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
            {detail.pipeline_stage_label && <span>{detail.pipeline_stage_label}</span>}
            {refreshing && <span>Updating…</span>}
            {lastUpdated && !refreshing && (
              <span>Updated {lastUpdated.toLocaleTimeString()}</span>
            )}
            <button type="button" className="owid-btn-secondary !min-h-0 px-2 py-1 text-xs" onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
        </div>

        {inActivePipeline && (
          <>
            <ClaimPipelineStepper currentKey={detail.pipeline_stage_key} pulsing={inActivePipeline} />
            <p className="text-xs text-[var(--muted)]">
              This page refreshes while the claim is being assessed and re-checked.
            </p>
          </>
        )}

        {assessmentDone && !inActivePipeline && (
          <p className="text-xs text-[var(--muted)]">
            {detail.staff_reviewed || detail.moderation_reviewed ? (
              <>
                <span className="font-medium text-[var(--fg)]">Staff-reviewed</span> — a moderator or admin has
                taken action on this record. Truth status can still change as new evidence arrives.
              </>
            ) : (
              <>
                <span className="font-medium text-[var(--fg)]">AI assessment</span> — automated from the claim library
                and submitted links, not human editorial sign-off for every claim. Truth status can be updated,
                disputed, or overturned as evidence shifts.
              </>
            )}
          </p>
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
          Sources, counterpoints, and contextual material from the library and any URLs submitted with this claim.
        </p>
        <div className="space-y-8">
          <EvidenceList title="Supporting" items={detail.evidence_supporting} variant="prominent" />
          <EvidenceList title="Contradicting" items={detail.evidence_contradicting} variant="prominent" />
          <EvidenceList title="Contextual" items={detail.evidence_contextual} variant="prominent" />
          {totalEvidence === 0 && (
            <p className="text-sm text-[var(--muted)]">
              {inActivePipeline
                ? "Gathering sources…"
                : "No sources matched yet."}
            </p>
          )}
        </div>
      </section>

      {graph && <ClaimGraphSection slug={slug} graph={graph} />}

      <section aria-labelledby="timeline-heading" className="space-y-4">
        <header>
          <h2 id="timeline-heading" className="owid-section-heading">
            Truth status over time
          </h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            How this living record has changed as assessments and evidence evolved.
          </p>
        </header>
        <ClaimTimeline events={timeline?.events ?? []} />
      </section>

      {detail.related_slugs.length > 0 && (
        <section aria-labelledby="related-heading" className="text-sm">
          <h2 id="related-heading" className="owid-kicker">
            Related in semantic space
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
            Assessment notes
          </h2>
          {detail.last_ai_run_at && (
            <p className="mt-1 text-xs text-[var(--muted)]">
              Last AI run:{" "}
              <time dateTime={detail.last_ai_run_at}>{formatLastAiRun(detail.last_ai_run_at)}</time>
            </p>
          )}
        </header>
        <AiAnalysisList items={detail.ai_analyses} />
        {detail.ai_analyses.length === 0 && inActivePipeline && (
          <p className="text-xs text-[var(--muted)]">Notes will appear when the assessment completes.</p>
        )}
        <ClaimStaffAiTools
          slug={slug}
          lastAiRunAt={detail.last_ai_run_at}
          generateAvailable={detail.generate_ai_analysis_available}
          blockReason={detail.generate_ai_analysis_block_reason}
        />
      </aside>
    </article>
  );
}
