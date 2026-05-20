"use client";

const STAGES: { key: string; label: string }[] = [
  { key: "received", label: "Received" },
  { key: "analyzing", label: "Analyzing" },
  { key: "gathering_evidence", label: "Gathering evidence" },
  { key: "ai_complete", label: "Complete (AI)" },
  { key: "moderated", label: "Moderated" },
];

type Props = {
  currentKey: string | null | undefined;
  pulsing?: boolean;
};

export function ClaimPipelineStepper({ currentKey, pulsing = false }: Props) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentKey);
  const activeIndex = currentIndex >= 0 ? currentIndex : 0;

  return (
    <ol className="flex flex-wrap gap-2 text-xs" aria-label="Research pipeline progress">
      {STAGES.map((stage, index) => {
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
