import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-[var(--border)] bg-[var(--bg-subtle)]">
      <div className="mx-auto max-w-content px-4 py-10 sm:px-6">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <p className="owid-display text-lg text-[var(--accent-dark)]">Rate My Claim</p>
            <p className="mt-2 max-w-sm text-sm leading-relaxed text-[var(--muted)]">
              Public claim pages with sources you can click. Less chatbot cosplay, more stuff that stays on the
              record.
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
              <li>
                <Link href="/atlas">Claim map</Link>
              </li>
            </ul>
          </div>
          <div>
            <p className="owid-kicker">What we&apos;re going for</p>
            <ul className="mt-3 space-y-2 text-sm text-[var(--muted)]">
              <li>Sources you can actually open</li>
              <li>No engagement bait or outrage loops</li>
              <li>Claims go live and can change as evidence rolls in</li>
            </ul>
          </div>
        </div>
        <p className="mt-8 border-t border-[var(--border)] pt-6 text-xs text-[var(--muted)]">
          Rate My Claim — calm publishing vibes, chaotic claim energy.
        </p>
      </div>
    </footer>
  );
}
