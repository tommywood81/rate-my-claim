"use client";

import { pipelineAgentState } from "@/lib/research-pipeline-ux";

type Props = {
  processingStatus: string | null | undefined;
  elapsedSec?: number;
  pollingHint?: string | null;
  compact?: boolean;
};

function AgentRow({
  label,
  status,
  percent,
  active,
}: {
  label: string;
  status: string;
  percent: number;
  active: boolean;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-semibold text-[var(--accent-dark)]">{label}</span>
        <span className="text-[var(--muted)]">{status}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded bg-white" aria-hidden>
        <div
          className={`h-full transition-all duration-500 ${active ? "bg-[var(--accent)]" : "bg-[var(--border)]"}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export function ResearchPipelineProgress({
  processingStatus,
  elapsedSec,
  pollingHint,
  compact = false,
}: Props) {
  const state = pipelineAgentState(processingStatus);
  const inFlight =
    processingStatus &&
    !["awaiting_moderation", "completed", "failed", "rejected", "revision_requested"].includes(
      processingStatus,
    );

  return (
    <div className={`space-y-3 ${compact ? "" : "rounded border border-[var(--border)] bg-white/80 p-3"}`}>
      <div className="flex items-center justify-between gap-2 text-xs text-[var(--muted)]">
        <span className="font-medium text-[var(--fg)]">Live pipeline</span>
        {typeof elapsedSec === "number" && inFlight && <span>{elapsedSec}s on this page</span>}
      </div>

      <div
        className="h-2 overflow-hidden rounded bg-white"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={state.overallPercent}
        aria-label="Overall research and decision progress"
      >
        <div
          className="h-full bg-[var(--accent-dark)] transition-all duration-500"
          style={{ width: `${state.overallPercent}%` }}
        />
      </div>

      <AgentRow
        label="Research agent"
        status={state.researchLabel}
        percent={state.researchPercent}
        active={state.researchPercent > 0 && state.researchPercent < 100}
      />
      <AgentRow
        label="Decision agent"
        status={state.decisionLabel}
        percent={state.decisionPercent}
        active={state.decisionPercent > 0 && state.decisionPercent < 100}
      />

      <p className="text-sm leading-relaxed text-[var(--muted)]">{state.detailMessage}</p>
      {pollingHint && (
        <p className="text-xs text-[var(--accent-warm)]">{pollingHint}</p>
      )}
    </div>
  );
}
