import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-[var(--border)] bg-[var(--bg-subtle)]">
      <div className="mx-auto max-w-content px-4 py-10 sm:px-6">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <p className="owid-display text-lg text-[var(--accent-dark)]">Rate My Claim</p>
            <p className="mt-2 max-w-sm text-sm leading-relaxed text-[var(--muted)]">
              Research and data to evaluate empirical claims. Evidence and moderation stay authoritative; AI assists
              interpretation.
            </p>
          </div>
          <div>
            <p className="owid-kicker">Explore</p>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link href="/claims">Browse claims</Link>
              </li>
              <li>
                <Link href="/search">Search</Link>
              </li>
              <li>
                <Link href="/submit">Submit a claim</Link>
              </li>
            </ul>
          </div>
          <div>
            <p className="owid-kicker">Principles</p>
            <ul className="mt-3 space-y-2 text-sm text-[var(--muted)]">
              <li>Open, evidence-first presentation</li>
              <li>No engagement farming or outrage mechanics</li>
              <li>All claims are live and may evolve over time</li>
            </ul>
          </div>
        </div>
        <p className="mt-8 border-t border-[var(--border)] pt-6 text-xs text-[var(--muted)]">
          Rate My Claim — local development build. Inspired by calm research publishing.
        </p>
      </div>
    </footer>
  );
}
