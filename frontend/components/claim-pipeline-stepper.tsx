"use client";

import { PIPELINE_STAGES } from "@/lib/research-pipeline-ux";

type Props = {
  currentKey: string | null | undefined;
  pulsing?: boolean;
  layout?: "horizontal" | "vertical";
};

export function ClaimPipelineStepper({
  currentKey,
  pulsing = false,
  layout = "horizontal",
}: Props) {
  let activeIndex = PIPELINE_STAGES.findIndex((s) => s.key === currentKey);
  if (activeIndex < 0) {
    if (currentKey === "failed" || currentKey === "rejected" || currentKey === "revised") {
      activeIndex = 3;
    } else {
      activeIndex = 0;
    }
  }

  if (layout === "vertical") {
    return (
      <ol className="space-y-2 text-sm" aria-label="Research pipeline progress">
        {PIPELINE_STAGES.map((stage, index) => {
          const done = index < activeIndex;
          const active = index === activeIndex;
          return (
            <li
              key={stage.key}
              className={`flex items-start gap-3 rounded border px-3 py-2 ${
                active
                  ? `border-[var(--accent-dark)] bg-white${pulsing ? " animate-pulse" : ""}`
                  : done
                    ? "border-[var(--border)] bg-white text-[var(--fg)]"
                    : "border-[var(--border)] bg-[var(--bg-subtle)] text-[var(--muted)]"
              }`}
              aria-current={active ? "step" : undefined}
            >
              <span
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  active
                    ? "bg-[var(--accent-dark)] text-white"
                    : done
                      ? "bg-[var(--accent)] text-white"
                      : "bg-[var(--border)] text-[var(--muted)]"
                }`}
                aria-hidden
              >
                {done ? "✓" : index + 1}
              </span>
              <span className={active ? "font-semibold text-[var(--accent-dark)]" : ""}>{stage.label}</span>
            </li>
          );
        })}
      </ol>
    );
  }

  return (
    <ol className="flex flex-wrap gap-2 text-xs" aria-label="Research pipeline progress">
      {PIPELINE_STAGES.map((stage, index) => {
        const done = index < activeIndex;
        const active = index === activeIndex;
        return (
          <li
            key={stage.key}
            className={`border px-2.5 py-1 ${
              active
                ? `border-[var(--accent-dark)] bg-[var(--accent-dark)] font-semibold text-white${pulsing ? " animate-pulse" : ""}`
                : done
                  ? "border-[var(--border)] bg-white text-[var(--fg)]"
                  : "border-[var(--border)] bg-[var(--bg-subtle)] text-[var(--muted)]"
            }`}
            aria-current={active ? "step" : undefined}
          >
            {stage.label}
          </li>
        );
      })}
    </ol>
  );
}
