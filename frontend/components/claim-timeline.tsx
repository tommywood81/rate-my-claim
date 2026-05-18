import Link from "next/link";

import type { TimelineEvent } from "@/lib/types";

const EVENT_LABELS: Record<TimelineEvent["event_type"], string> = {
  confidence_evolution: "Confidence",
  moderation: "Moderation",
  evidence: "Evidence",
  contradiction_emergence: "Contradiction",
  freshness_decay: "Freshness",
};

const EVENT_COLORS: Record<TimelineEvent["event_type"], string> = {
  confidence_evolution: "border-l-[var(--accent)]",
  moderation: "border-l-violet-700",
  evidence: "border-l-emerald-700",
  contradiction_emergence: "border-l-amber-600",
  freshness_decay: "border-l-slate-500",
};

type ClaimTimelineProps = {
  events: TimelineEvent[];
};

export function ClaimTimeline({ events }: ClaimTimelineProps) {
  if (!events.length) {
    return <p className="text-sm text-[var(--muted)]">No timeline events recorded yet.</p>;
  }

  return (
    <ol className="relative space-y-0 border-l border-[var(--border)] pl-6">
      {events.map((ev) => {
        const otherSlug = ev.payload.other_slug as string | undefined;
        return (
          <li key={ev.id} className="pb-6 last:pb-0">
            <span
              className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-[var(--accent)]"
              aria-hidden
            />
            <article
              className={`rounded border border-[var(--border)] border-l-4 bg-white p-3 ${EVENT_COLORS[ev.event_type]}`}
            >
              <header className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-sm font-medium">{ev.title}</h3>
                <time dateTime={ev.timestamp} className="text-xs text-[var(--muted)]">
                  {new Date(ev.timestamp).toLocaleString()}
                </time>
              </header>
              <p className="mt-1 text-xs uppercase tracking-wide text-[var(--muted)]">
                {EVENT_LABELS[ev.event_type]}
              </p>
              {ev.description && <p className="mt-2 text-sm text-[var(--fg)]">{ev.description}</p>}
              {otherSlug && (
                <p className="mt-2 text-xs">
                  <Link href={`/claims/${otherSlug}`} className="underline">
                    View related claim
                  </Link>
                </p>
              )}
            </article>
          </li>
        );
      })}
    </ol>
  );
}
