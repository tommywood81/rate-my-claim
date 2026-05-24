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
        <p className="font-semibold">Our read: this looks supported</p>
        <p className="mt-1 text-emerald-900/90">
          Matched sources lean yes given what we have on file. Still worth clicking the links — and the page can
          change as new evidence shows up.
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
        <p className="font-semibold">Our read: this looks refuted</p>
        <p className="mt-1 text-amber-900/90">
          Matched sources don&apos;t back the claim as stated. Check the contradicting evidence and summary for
          nuance.
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
      <p className="font-semibold">Our read: inconclusive</p>
      <p className="mt-1 text-[var(--muted)]">
        Not enough sources in the library yet to call it clearly either way.
      </p>
    </div>
  );
}
