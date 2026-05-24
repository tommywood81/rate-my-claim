/** User-facing copy and progress for live research / decision pipeline. */

import type { ClaimDetail } from "@/lib/types";

export const PIPELINE_STAGES = [
  { key: "received", label: "Received", hint: "Claim registered and published live." },
  { key: "analyzing", label: "Analyzing", hint: "Embedding, duplicate check, and canonical wording." },
  { key: "gathering_evidence", label: "Gathering evidence", hint: "Archive search, URLs, and research pass." },
  { key: "assessed", label: "Assessment complete", hint: "Automated research and verdict are on your claim page." },
] as const;

export type PipelineStageKey = (typeof PIPELINE_STAGES)[number]["key"];

export const SUBMIT_STEP_LABELS = [
  "Validating claim text",
  "Creating live claim page",
  "Queueing research & decision agents",
  "Opening your live claim",
] as const;

export const PIPELINE_TERMINAL = new Set([
  "awaiting_moderation",
  "completed",
  "failed",
  "rejected",
  "revision_requested",
]);

export type PipelineAgentState = {
  overallPercent: number;
  researchPercent: number;
  decisionPercent: number;
  researchLabel: string;
  decisionLabel: string;
  detailMessage: string;
};

const DEFAULT_IDLE: PipelineAgentState = {
  overallPercent: 0,
  researchPercent: 0,
  decisionPercent: 0,
  researchLabel: "Idle",
  decisionLabel: "Idle",
  detailMessage: "Pipeline not started.",
};

/** Mirror backend pipeline_labels.processing_status → stepper key. */
export function processingStatusToStageKey(
  processingStatus: string | null | undefined,
): PipelineStageKey | null {
  switch (processingStatus) {
    case "submitted":
      return "received";
    case "embedding":
    case "duplicate_check":
    case "canonicalizing":
      return "analyzing";
    case "enriching":
      return "gathering_evidence";
    case "awaiting_moderation":
    case "completed":
      return "assessed";
    case "revision_requested":
      return "revised" as PipelineStageKey;
    case "failed":
      return "failed" as PipelineStageKey;
    case "rejected":
      return "rejected" as PipelineStageKey;
    default:
      return null;
  }
}

export function pipelineStageIndex(stageKey: string | null | undefined): number {
  if (!stageKey) return -1;
  return PIPELINE_STAGES.findIndex((s) => s.key === stageKey);
}

/** Map backend processing_status to dual-agent progress (frontend-only). */
export function pipelineAgentState(processingStatus: string | null | undefined): PipelineAgentState {
  switch (processingStatus) {
    case "submitted":
      return {
        overallPercent: 10,
        researchPercent: 15,
        decisionPercent: 0,
        researchLabel: "Queued — preparing workspace",
        decisionLabel: "Standing by",
        detailMessage: "Your claim is registered and will enter automated research shortly.",
      };
    case "embedding":
      return {
        overallPercent: 22,
        researchPercent: 30,
        decisionPercent: 0,
        researchLabel: "Building semantic index",
        decisionLabel: "Standing by",
        detailMessage: "Embedding the claim so we can find similar evidence in the archive.",
      };
    case "duplicate_check":
      return {
        overallPercent: 32,
        researchPercent: 42,
        decisionPercent: 0,
        researchLabel: "Checking for duplicates",
        decisionLabel: "Standing by",
        detailMessage: "Comparing against existing claims before enrichment continues.",
      };
    case "canonicalizing":
      return {
        overallPercent: 42,
        researchPercent: 55,
        decisionPercent: 5,
        researchLabel: "Normalizing claim wording",
        decisionLabel: "Warming up",
        detailMessage: "Turning your submission into a clear, testable canonical claim.",
      };
    case "enriching":
      return {
        overallPercent: 68,
        researchPercent: 78,
        decisionPercent: 35,
        researchLabel: "Gathering evidence & sources",
        decisionLabel: "Drafting assessment",
        detailMessage:
          "Ingesting URLs, searching the corpus, and running confidence / verdict analysis.",
      };
    case "awaiting_moderation":
    case "completed":
      return {
        overallPercent: 100,
        researchPercent: 100,
        decisionPercent: 100,
        researchLabel: "Assessment complete",
        decisionLabel: "Assessment complete",
        detailMessage:
          "Automated research finished. Scores, summary, and any matched sources are on your live claim page.",
      };
    case "failed":
      return {
        overallPercent: 0,
        researchPercent: 0,
        decisionPercent: 0,
        researchLabel: "Interrupted",
        decisionLabel: "Interrupted",
        detailMessage: "Assessment failed. Staff can re-run the pipeline from the maintenance queue.",
      };
    case "rejected":
      return {
        overallPercent: 0,
        researchPercent: 0,
        decisionPercent: 0,
        researchLabel: "Withdrawn",
        decisionLabel: "Withdrawn",
        detailMessage: "This submission was withdrawn from the public catalog.",
      };
    case "revision_requested":
      return {
        overallPercent: 50,
        researchPercent: 50,
        decisionPercent: 0,
        researchLabel: "Revision requested",
        decisionLabel: "Paused",
        detailMessage: "Waiting for an updated submission before research continues.",
      };
    default:
      return DEFAULT_IDLE;
  }
}

export type SubmitTrackContext = {
  elapsedSec: number;
  sourceUrlCount: number;
  indexedClaims?: number;
};

/** Active-step line under the vertical stepper on the submit page. */
export function submitActiveStageMessage(
  processingStatus: string | null | undefined,
  ctx: SubmitTrackContext,
): string {
  const n = ctx.indexedClaims;
  const archive =
    n != null && n > 0
      ? `Searching ${n} indexed claim${n === 1 ? "" : "s"} in the archive…`
      : "Searching the embedding archive…";

  switch (processingStatus) {
    case "submitted":
      return "Queued — your claim is already live on the site.";
    case "embedding":
      return `Indexing wording. ${archive}`;
    case "duplicate_check":
      return "Checking for near-duplicate claims in the corpus…";
    case "canonicalizing":
      return "Turning your text into a clear, testable canonical claim…";
    case "enriching":
      if (ctx.sourceUrlCount > 0) {
        return `Reading ${ctx.sourceUrlCount} linked source${ctx.sourceUrlCount === 1 ? "" : "s"}, ${archive.toLowerCase()} Running AI verdict pass (often 20–40s).`;
      }
      return `${archive} Running AI confidence and verdict (often 20–40s).`;
    case "awaiting_moderation":
    case "completed":
      return "Assessment complete — open your live claim page for the verdict and sources.";
    case "failed":
      return "Pipeline interrupted — you can still open the live claim or ask staff to re-run enrichment.";
    case "revision_requested":
      return "An updated submission is needed before research continues.";
    case "rejected":
      return "This submission was withdrawn from the public catalog.";
    default:
      return "Connecting to the research pipeline…";
  }
}

export type SubmitOutcome = { id: string; text: string };

/** Concrete outcomes to show as checkmarks while polling the live claim. */
export function buildSubmitOutcomes(
  detail: ClaimDetail | null,
  extras: {
    duplicateCount?: number;
    canonicalCandidate?: string | null;
    errorMessage?: string | null;
  },
): SubmitOutcome[] {
  const out: SubmitOutcome[] = [];
  if (!detail && !extras.errorMessage) return out;

  if (detail?.public_slug) {
    out.push({ id: "live", text: "Live claim page created — visible on Browse." });
  }
  const canonical = detail?.canonical_claim_text?.trim() || extras.canonicalCandidate?.trim();
  if (canonical) {
    const short = canonical.length > 140 ? `${canonical.slice(0, 137)}…` : canonical;
    out.push({ id: "canonical", text: `Canonical claim: “${short}”` });
  }
  const dup = extras.duplicateCount ?? detail?.related_slugs?.length ?? 0;
  if (dup > 0) {
    out.push({
      id: "duplicates",
      text: `${dup} similar claim${dup === 1 ? "" : "s"} flagged in the archive.`,
    });
  } else if (
    detail?.processing_status &&
    ["duplicate_check", "canonicalizing", "enriching", "awaiting_moderation", "completed"].includes(
      detail.processing_status,
    )
  ) {
    out.push({ id: "duplicates-none", text: "No close duplicates found in the archive." });
  }
  if (detail?.evidence_count && detail.evidence_count > 0) {
    out.push({
      id: "evidence",
      text: `${detail.evidence_count} source${detail.evidence_count === 1 ? "" : "s"} matched on record.`,
    });
  }
  const summary = detail?.live_ai_summary?.trim();
  if (summary) {
    const short = summary.length > 160 ? `${summary.slice(0, 157)}…` : summary;
    out.push({ id: "summary", text: `Research summary: ${short}` });
  }
  if (detail?.truth_label && detail.truth_label !== "unclear") {
    out.push({
      id: "truth",
      text: `Assessment: ${detail.truth_label} (AI + archive).`,
    });
  } else if (
    detail?.processing_status === "awaiting_moderation" ||
    detail?.processing_status === "completed"
  ) {
    out.push({ id: "truth-unclear", text: "Assessment: inconclusive or limited sources." });
  }
  if (extras.errorMessage?.trim()) {
    out.push({ id: "error", text: extras.errorMessage.trim() });
  }
  return out;
}

/** Submit-form status line with elapsed-time hints (initial POST only). */
export function submitStatusMessage(elapsedSec: number, stepIndex: number): string {
  if (elapsedSec >= 20) {
    return "Almost there — finishing setup on the server…";
  }
  if (elapsedSec >= 10) {
    return "Still processing your submission (10–30s is normal)…";
  }
  if (elapsedSec >= 5) {
    return "Waiting for server response…";
  }
  const idx = Math.min(stepIndex, SUBMIT_STEP_LABELS.length - 1);
  return SUBMIT_STEP_LABELS[idx];
}

/** Extra hint on claim page when polling takes longer than expected. */
export function claimPollingHint(
  elapsedSec: number,
  processingStatus: string | null | undefined,
): string | null {
  if (!processingStatus || PIPELINE_TERMINAL.has(processingStatus)) {
    return null;
  }
  if (elapsedSec >= 45) {
    return "Taking longer than usual — the research agent may be waiting on the AI provider or URL ingestion.";
  }
  if (elapsedSec >= 20) {
    return "Still running — gathering evidence and running the assessment model.";
  }
  return null;
}

export function isPipelineInFlight(processingStatus: string | null | undefined): boolean {
  return Boolean(processingStatus && !PIPELINE_TERMINAL.has(processingStatus));
}

export function isAssessmentComplete(detail: ClaimDetail | null | undefined): boolean {
  if (!detail) return false;
  if (detail.assessment_complete) return true;
  const proc = detail.processing_status;
  return proc === "completed" || proc === "awaiting_moderation";
}
