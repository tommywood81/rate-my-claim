"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { AiAnalysisList } from "@/components/ai-analysis-list";
import { EvidenceList } from "@/components/evidence-list";
import { isAssessmentComplete } from "@/lib/research-pipeline-ux";
import type { ClaimDetail, EvidenceItem } from "@/lib/types";

type EvidenceTab = "all" | "supporting" | "contradicting" | "contextual";

type Props = {
  slug: string;
  detail: ClaimDetail | null;
  elapsedSec: number;
  inFlight: boolean;
};

const VERDICT_HEADLINE: Record<NonNullable<ClaimDetail["truth_label"]>, string> = {
  supported: "Supported",
  refuted: "Refuted",
  unclear: "Inconclusive",
};

function allEvidence(detail: ClaimDetail): EvidenceItem[] {
  return [
    ...detail.evidence_supporting,
    ...detail.evidence_contradicting,
    ...detail.evidence_contextual,
  ];
}

function tabItems(detail: ClaimDetail, tab: EvidenceTab): EvidenceItem[] {
  switch (tab) {
    case "supporting":
      return detail.evidence_supporting;
    case "contradicting":
      return detail.evidence_contradicting;
    case "contextual":
      return detail.evidence_contextual;
    default:
      return allEvidence(detail);
  }
}

function tabTitle(tab: EvidenceTab): string {
  switch (tab) {
    case "supporting":
      return "Supporting";
    case "contradicting":
      return "Contradicting";
    case "contextual":
      return "Contextual";
    default:
      return "All sources";
  }
}

export function SubmitClaimResultsPanel({ slug, detail, elapsedSec, inFlight }: Props) {
  const [evidenceTab, setEvidenceTab] = useState<EvidenceTab>("all");
  const [showNotes, setShowNotes] = useState(false);
  const [verdictPulse, setVerdictPulse] = useState(false);
  const [evidenceBump, setEvidenceBump] = useState(false);
  const hadVerdict = useRef(false);
  const verdictRef = useRef<HTMLDivElement>(null);
  const prevEvidenceCount = useRef(0);

  const complete = isAssessmentComplete(detail);
  const totalEvidence = detail
    ? detail.evidence_supporting.length +
      detail.evidence_contradicting.length +
      detail.evidence_contextual.length
    : 0;

  const tabs = useMemo(
    () =>
      [
        { id: "all" as const, count: totalEvidence },
        { id: "supporting" as const, count: detail?.evidence_supporting.length ?? 0 },
        { id: "contradicting" as const, count: detail?.evidence_contradicting.length ?? 0 },
        { id: "contextual" as const, count: detail?.evidence_contextual.length ?? 0 },
      ].filter((t) => t.id === "all" || t.count > 0),
    [detail, totalEvidence],
  );

  useEffect(() => {
    if (detail?.truth_label && !hadVerdict.current) {
      hadVerdict.current = true;
      setVerdictPulse(true);
      verdictRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      const t = setTimeout(() => setVerdictPulse(false), 2400);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [detail?.truth_label]);

  useEffect(() => {
    if (totalEvidence > prevEvidenceCount.current) {
      prevEvidenceCount.current = totalEvidence;
      if (totalEvidence > 0) {
        setEvidenceBump(true);
        const t = setTimeout(() => setEvidenceBump(false), 900);
        return () => clearTimeout(t);
      }
    }
    return undefined;
  }, [totalEvidence]);

  useEffect(() => {
    if (complete && detail?.ai_analyses.length) {
      setShowNotes(true);
    }
  }, [complete, detail?.ai_analyses.length]);

  if (!detail) {
    return (
      <section
        className="submit-results-panel space-y-4 border-t border-[var(--border)] pt-6"
        aria-label="Assessment results"
      >
        <p className="text-sm font-medium text-[var(--fg)]">Your assessment</p>
        <div className="submit-results-skeleton space-y-3 rounded-lg border border-[var(--border)] bg-white p-5">
          <div className="h-8 w-2/3 max-w-xs animate-pulse rounded bg-[var(--bg-subtle)]" />
          <div className="h-4 w-full animate-pulse rounded bg-[var(--bg-subtle)]" />
          <div className="h-4 w-5/6 animate-pulse rounded bg-[var(--bg-subtle)]" />
          <p className="pt-2 text-xs text-[var(--muted)]">Waiting for the first assessment data…</p>
        </div>
      </section>
    );
  }

  const claimHref = `/claims/${encodeURIComponent(slug)}`;
  const listed = tabItems(detail, evidenceTab);
  const verdictLabel = detail.truth_label;

  return (
    <section
      id="submit-live-results"
      className="submit-results-panel space-y-6 border-t border-[var(--border)] pt-6 scroll-mt-6"
      aria-label="Assessment results"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="owid-kicker">
            {complete ? "Assessment complete" : "Live assessment"}
            {complete ? " · AI assessment" : ""}
          </p>
          <h2 className="owid-section-heading mt-1 text-xl sm:text-2xl">Your results</h2>
        </div>
        {complete && (
          <p className="text-xs text-[var(--muted)]">
            Finished in {elapsedSec}s ·{" "}
            <Link href={claimHref} className="font-medium text-[var(--accent)] hover:underline">
              Permalink
            </Link>
          </p>
        )}
      </div>

      <blockquote className="border-l-4 border-[var(--accent-dark)] pl-4 text-base font-medium leading-snug text-[var(--fg)]">
        {detail.canonical_claim_text}
      </blockquote>

      {verdictLabel ? (
        <div
          ref={verdictRef}
          className={`submit-verdict-hero submit-verdict-hero--${verdictLabel} ${
            verdictPulse ? "submit-verdict-hero--pulse" : ""
          }`}
        >
          <p className="text-xs font-semibold uppercase tracking-widest opacity-80">Truth status</p>
          <p className="owid-display mt-1 text-3xl sm:text-4xl">{VERDICT_HEADLINE[verdictLabel]}</p>
          <p className="mt-3 text-sm leading-relaxed opacity-90">
            {verdictLabel === "supported" &&
              "Current sources and counterpoints lean toward support — this can change as new evidence arrives."}
            {verdictLabel === "refuted" &&
              "Current sources do not support the claim as stated. Review the evidence below."}
            {verdictLabel === "unclear" &&
              "Not enough on record for a clear call yet. The library may fill in more over time."}
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-[var(--accent)]/40 bg-white/80 px-4 py-6 text-center">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" />
          <p className="mt-2 text-sm font-medium text-[var(--fg)]">Drafting truth status…</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Sources and scores may appear before the final call.
          </p>
        </div>
      )}

      <dl className="owid-stat-grid submit-results-stats">
        <div className="owid-stat">
          <dt>Assessment confidence</dt>
          <dd>{detail.confidence_score.toFixed(2)}</dd>
        </div>
        <div className="owid-stat">
          <dt>Evidence score</dt>
          <dd>{detail.evidence_score.toFixed(2)}</dd>
        </div>
        <div className="owid-stat">
          <dt>Controversy</dt>
          <dd>{detail.controversy_score.toFixed(2)}</dd>
        </div>
        <div className="owid-stat">
          <dt>Freshness</dt>
          <dd>{detail.freshness_score.toFixed(2)}</dd>
        </div>
      </dl>

      {detail.live_ai_summary && (
        <div className="submit-results-reveal rounded-lg border border-[var(--accent)]/25 bg-[var(--accent-soft)]/50 p-4 sm:p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--accent-dark)]">
            Research summary
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[var(--fg)]">{detail.live_ai_summary}</p>
        </div>
      )}

      <div className="owid-panel-evidence space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="owid-section-heading text-lg">Evidence</h3>
          <p className="text-sm text-[var(--muted)]">
            <span className={evidenceBump ? "submit-evidence-count--bump" : ""}>
              {totalEvidence} source{totalEvidence === 1 ? "" : "s"}
            </span>
            {inFlight && !complete ? " · still gathering" : ""}
          </p>
        </div>

        {tabs.length > 1 && (
          <div className="flex flex-wrap gap-2" role="tablist" aria-label="Evidence categories">
            {tabs.map((t) => {
              const active = evidenceTab === t.id;
              const label =
                t.id === "all"
                  ? `All (${t.count})`
                  : `${tabTitle(t.id)} (${t.count})`;
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className={`owid-chip text-xs transition-colors ${
                    active ? "owid-chip-active" : ""
                  }`}
                  onClick={() => setEvidenceTab(t.id)}
                >
                  {label}
                </button>
              );
            })}
          </div>
        )}

        {listed.length > 0 ? (
          evidenceTab === "all" ? (
            <div className="space-y-8">
              <EvidenceList title="Supporting" items={detail.evidence_supporting} variant="prominent" />
              <EvidenceList title="Contradicting" items={detail.evidence_contradicting} variant="prominent" />
              <EvidenceList title="Contextual" items={detail.evidence_contextual} variant="prominent" />
            </div>
          ) : (
            <EvidenceList title={tabTitle(evidenceTab)} items={listed} variant="prominent" />
          )
        ) : (
          <p className="text-sm text-[var(--muted)]">
            {inFlight ? "Searching the claim library for sources…" : "No library sources matched yet."}
          </p>
        )}
      </div>

      {(detail.ai_analyses.length > 0 || complete) && (
        <div className="owid-panel-ai space-y-3">
          <button
            type="button"
            className="flex w-full items-center justify-between gap-2 text-left"
            aria-expanded={showNotes}
            onClick={() => setShowNotes((v) => !v)}
          >
            <span className="owid-kicker">Assessment notes</span>
            <span className="text-xs text-[var(--accent)]">{showNotes ? "Hide" : "Show"}</span>
          </button>
          {showNotes && <AiAnalysisList items={detail.ai_analyses} />}
        </div>
      )}

      {complete && (
        <p className="submit-results-reveal text-center text-sm text-[var(--muted)]">
          This living record stays on the site — truth status can change as new evidence arrives.{" "}
          <Link href={claimHref} className="font-semibold text-[var(--accent-dark)] hover:underline">
            Share or bookmark your claim page →
          </Link>
        </p>
      )}
    </section>
  );
}
