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
        <p className="font-semibold">Assessment: this claim appears true</p>
        <p className="mt-1 text-emerald-900/90">
          Automated research supports the statement given current evidence and consensus. Moderators may
          still refine sources and scores.
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
        <p className="font-semibold">Assessment: this claim appears false</p>
        <p className="mt-1 text-amber-900/90">
          Automated research does not support the statement as stated. Review evidence and the research
          summary for detail.
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
      <p className="font-semibold">Assessment: inconclusive</p>
      <p className="mt-1 text-[var(--muted)]">
        Not enough evidence in the archive to call the claim clearly true or false yet.
      </p>
    </div>
  );
}
