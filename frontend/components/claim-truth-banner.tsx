type TruthLabel = "supported" | "refuted" | "unclear";

type Props = {
  label: TruthLabel;
};

export function ClaimTruthBanner({ label }: Props) {
  if (label === "supported") {
    return (
      <div
        className="rounded border border-emerald-700/35 bg-emerald-50 px-4 py-3 text-sm text-emerald-950"
        role="status"
        aria-live="polite"
      >
        <p className="font-semibold">Truth status: supported</p>
        <p className="mt-1 text-emerald-900/90">
          Current sources and counterpoints lean toward support given what is on record. This can change as new
          evidence arrives or the claim is re-checked.
        </p>
      </div>
    );
  }

  if (label === "refuted") {
    return (
      <div
        className="rounded border border-amber-700/40 bg-amber-50 px-4 py-3 text-sm text-amber-950"
        role="status"
        aria-live="polite"
      >
        <p className="font-semibold">Truth status: refuted</p>
        <p className="mt-1 text-amber-900/90">
          Current sources do not support the claim as stated. Review contradicting evidence and the summary — status
          may shift if new information appears.
        </p>
      </div>
    );
  }

  return (
    <div
      className="rounded border border-[var(--border)] bg-[var(--bg-subtle)] px-4 py-3 text-sm text-[var(--fg)]"
      role="status"
      aria-live="polite"
    >
      <p className="font-semibold">Truth status: inconclusive</p>
      <p className="mt-1 text-[var(--muted)]">
        Evidence and scores are too mixed or middling for a clear supported/refuted call — a contested edge case.
        Status can change when new sources are added or the claim is re-assessed.
      </p>
    </div>
  );
}
