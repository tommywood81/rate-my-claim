import { SiteAuthNav } from "@/components/site-auth-nav";

const navLink =
  "rounded px-2 py-1 text-[var(--muted)] hover:text-[var(--fg)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]";

export function SiteHeader() {
  return (
    <header className="border-b border-[var(--border)] bg-[var(--card)]">
      <a
        href="#main-content"
        className="skip-link absolute left-2 top-2 z-50 -translate-y-16 rounded bg-[var(--accent)] px-3 py-2 text-sm text-white focus:translate-y-0"
      >
        Skip to main content
      </a>
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
        <a
          href="/"
          className="text-lg font-semibold tracking-tight text-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Rate My Claim
        </a>
        <nav className="flex flex-1 flex-wrap items-center justify-end gap-1 text-sm sm:gap-2" aria-label="Primary">
          <a href="/claims" className={navLink}>
            Browse
          </a>
          <a href="/search" className={navLink}>
            Search
          </a>
          <a href="/submit" className={navLink}>
            Submit
          </a>
          <a href="/moderation" className={navLink}>
            Moderation
          </a>
          <span className="hidden flex-1 sm:inline" aria-hidden />
          <SiteAuthNav />
        </nav>
      </div>
    </header>
  );
}
