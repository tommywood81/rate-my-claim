/** User-facing copy and progress for live claim checks. */



import type { ClaimDetail } from "@/lib/types";



export const PIPELINE_STAGES = [

  { key: "received", label: "Received", hint: "Your claim is on the site." },

  { key: "analyzing", label: "Analyzing", hint: "Checking wording and whether we've seen this before." },

  { key: "gathering_evidence", label: "Gathering evidence", hint: "Reading your links and searching the claim library." },

  { key: "assessed", label: "Assessment complete", hint: "Truth status, scores, and sources are on your claim page." },

] as const;



export type PipelineStageKey = (typeof PIPELINE_STAGES)[number]["key"];



export const SUBMIT_STEP_LABELS = [

  "Checking your claim text",

  "Creating your live page",

  "Starting the background check",

  "Almost done",

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

  researchLabel: "Waiting",

  decisionLabel: "Waiting",

  detailMessage: "Not started yet.",

};



function formatTruthLabel(label: string): string {

  switch (label) {

    case "supported":

      return "looks supported";

    case "refuted":

      return "looks refuted";

    default:

      return "inconclusive";

  }

}



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



/** Map backend processing_status to dual-track progress (frontend-only). */

export function pipelineAgentState(processingStatus: string | null | undefined): PipelineAgentState {

  switch (processingStatus) {

    case "submitted":

      return {

        overallPercent: 10,

        researchPercent: 15,

        decisionPercent: 0,

        researchLabel: "Queued",

        decisionLabel: "Standing by",

        detailMessage: "Your claim is live. The check starts in a moment.",

      };

    case "embedding":

      return {

        overallPercent: 22,

        researchPercent: 30,

        decisionPercent: 0,

        researchLabel: "Matching similar claims",

        decisionLabel: "Standing by",

        detailMessage: "Finding related claims in the library.",

      };

    case "duplicate_check":

      return {

        overallPercent: 32,

        researchPercent: 42,

        decisionPercent: 0,

        researchLabel: "Duplicate check",

        decisionLabel: "Standing by",

        detailMessage: "Making sure we're not filing the same claim twice.",

      };

    case "canonicalizing":

      return {

        overallPercent: 42,

        researchPercent: 55,

        decisionPercent: 5,

        researchLabel: "Cleaning up wording",

        decisionLabel: "Warming up",

        detailMessage: "Turning your submission into a clear, testable statement.",

      };

    case "enriching":

      return {

        overallPercent: 68,

        researchPercent: 78,

        decisionPercent: 35,

        researchLabel: "Finding sources",

        decisionLabel: "Drafting assessment",

        detailMessage: "Reading links, searching the library, and running the AI pass.",

      };

    case "awaiting_moderation":

    case "completed":

      return {

        overallPercent: 100,

        researchPercent: 100,

        decisionPercent: 100,

        researchLabel: "Done",

        decisionLabel: "Done",

        detailMessage: "Assessment complete. Truth status, scores, and matched sources are on your claim page.",

      };

    case "failed":

      return {

        overallPercent: 0,

        researchPercent: 0,

        decisionPercent: 0,

        researchLabel: "Interrupted",

        decisionLabel: "Interrupted",

        detailMessage: "Something broke mid-check. The claim page is still live — staff can retry.",

      };

    case "rejected":

      return {

        overallPercent: 0,

        researchPercent: 0,

        decisionPercent: 0,

        researchLabel: "Withdrawn",

        decisionLabel: "Withdrawn",

        detailMessage: "This submission was removed from the public catalog.",

      };

    case "revision_requested":

      return {

        overallPercent: 50,

        researchPercent: 50,

        decisionPercent: 0,

        researchLabel: "Needs an edit",

        decisionLabel: "Paused",

        detailMessage: "Waiting for an updated submission before the check continues.",

      };

    default:

      return DEFAULT_IDLE;

  }

}



export type SubmitTrackContext = {

  elapsedSec: number;

  indexedClaims?: number;

};



/** Active-step line under the vertical stepper on the submit page. */

export function submitActiveStageMessage(

  processingStatus: string | null | undefined,

  ctx: SubmitTrackContext,

): string {

  const n = ctx.indexedClaims;

  const librarySearch =

    n != null && n > 0

      ? `Searching ${n} claim${n === 1 ? "" : "s"} already in the library…`

      : "Searching the claim library…";



  switch (processingStatus) {

    case "submitted":

      return "Queued — your claim is already live on the site.";

    case "embedding":

      return `Matching wording. ${librarySearch}`;

    case "duplicate_check":

      return "Checking for near-duplicates…";

    case "canonicalizing":

      return "Sharpening the wording into a clear, testable claim…";

    case "enriching":

      return `${librarySearch} Running the AI pass (often 20–40s).`;

    case "awaiting_moderation":

    case "completed":

      return "Assessment complete — open your claim page for truth status and sources.";

    case "failed":

      return "Check interrupted — you can still open the live claim page.";

    case "revision_requested":

      return "We need an updated submission before the check continues.";

    case "rejected":

      return "This submission was withdrawn from the public catalog.";

    default:

      return "Connecting…";

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

    out.push({ id: "live", text: "Living record published — visible on Browse." });

  }

  const canonical = detail?.canonical_claim_text?.trim() || extras.canonicalCandidate?.trim();

  if (canonical) {

    const short = canonical.length > 140 ? `${canonical.slice(0, 137)}…` : canonical;

    out.push({ id: "canonical", text: `Wording locked in: “${short}”` });

  }

  const dup = extras.duplicateCount ?? detail?.related_slugs?.length ?? 0;

  if (dup > 0) {

    out.push({

      id: "duplicates",

      text: `${dup} similar claim${dup === 1 ? "" : "s"} already in the library.`,

    });

  } else if (

    detail?.processing_status &&

    ["duplicate_check", "canonicalizing", "enriching", "awaiting_moderation", "completed"].includes(

      detail.processing_status,

    )

  ) {

    out.push({ id: "duplicates-none", text: "No close duplicates found." });

  }

  if (detail?.evidence_count && detail.evidence_count > 0) {

    out.push({

      id: "evidence",

      text: `${detail.evidence_count} source${detail.evidence_count === 1 ? "" : "s"} matched so far.`,

    });

  }

  const summary = detail?.live_ai_summary?.trim();

  if (summary) {

    const short = summary.length > 160 ? `${summary.slice(0, 157)}…` : summary;

    out.push({ id: "summary", text: `Summary: ${short}` });

  }

  if (detail?.truth_label && detail.truth_label !== "unclear") {

    out.push({

      id: "truth",

      text: `Truth status: ${formatTruthLabel(detail.truth_label)} (from matched sources and assessment).`,

    });

  } else if (

    detail?.processing_status === "awaiting_moderation" ||

    detail?.processing_status === "completed"

  ) {

    out.push({ id: "truth-unclear", text: "Truth status: inconclusive — not enough sources yet." });

  }

  if (extras.errorMessage?.trim()) {

    out.push({ id: "error", text: extras.errorMessage.trim() });

  }

  return out;

}



/** Submit-form status line with elapsed-time hints (initial POST only). */

export function submitStatusMessage(elapsedSec: number, stepIndex: number): string {

  if (elapsedSec >= 20) {

    return "Almost there — finishing up on the server…";

  }

  if (elapsedSec >= 10) {

    return "Still working (10–30s is normal)…";

  }

  if (elapsedSec >= 5) {

    return "Waiting for the server…";

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

    return "Taking longer than usual — probably waiting on a slow link or the AI provider.";

  }

  if (elapsedSec >= 20) {

    return "Still running — gathering sources and drafting the assessment.";

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

