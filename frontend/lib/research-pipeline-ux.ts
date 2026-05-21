/** User-facing copy and progress for live research / decision pipeline. */

export const SUBMIT_STEP_LABELS = [
  "Validating claim text",
  "Creating live claim page",
  "Queueing research & decision agents",
  "Opening your live claim",
] as const;

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
      return {
        overallPercent: 100,
        researchPercent: 100,
        decisionPercent: 100,
        researchLabel: "Research complete",
        decisionLabel: "Decision ready",
        detailMessage:
          "Automated research and AI decision pass are done. A moderator may still refine scores and citations.",
      };
    case "completed":
      return {
        overallPercent: 100,
        researchPercent: 100,
        decisionPercent: 100,
        researchLabel: "Reviewed",
        decisionLabel: "Reviewed",
        detailMessage: "A moderator has marked this claim reviewed.",
      };
    case "failed":
      return {
        overallPercent: 0,
        researchPercent: 0,
        decisionPercent: 0,
        researchLabel: "Interrupted",
        decisionLabel: "Interrupted",
        detailMessage: "Enrichment failed. Moderators can re-run the pipeline from the review queue.",
      };
    case "rejected":
      return {
        overallPercent: 0,
        researchPercent: 0,
        decisionPercent: 0,
        researchLabel: "Withdrawn",
        decisionLabel: "Withdrawn",
        detailMessage: "This submission was withdrawn from the public queue.",
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

/** Submit-form status line with elapsed-time hints. */
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
export function claimPollingHint(elapsedSec: number, processingStatus: string | null | undefined): string | null {
  if (!processingStatus || processingStatus === "awaiting_moderation" || processingStatus === "completed") {
    return null;
  }
  if (elapsedSec >= 45) {
    return "Taking longer than usual — the research agent may be waiting on the AI provider or URL ingestion.";
  }
  if (elapsedSec >= 20) {
    return "Still running — gathering evidence and running the decision model.";
  }
  return null;
}
