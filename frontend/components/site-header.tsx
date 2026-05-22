import { SiteAuthNav } from "@/components/site-auth-nav";

const navLink = "owid-nav-link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-white/95 backdrop-blur-sm">
      <a
        href="#main-content"
        className="skip-link absolute left-2 top-2 z-50 -translate-y-16 rounded-sm bg-[var(--accent-dark)] px-3 py-2 text-sm text-white focus:translate-y-0"
      >
        Skip to main content
      </a>
      <div className="mx-auto flex max-w-content items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <a
          href="/"
          className="owid-display text-xl text-[var(--accent-dark)] no-underline hover:text-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Rate My Claim
        </a>
        <nav className="flex flex-1 flex-wrap items-center justify-end gap-0.5 sm:gap-1" aria-label="Primary">
          <a href="/claims" className={navLink}>
            Browse
          </a>
          <a href="/search" className={navLink}>
            Search
          </a>
          <a href="/atlas" className={navLink}>
            Data model
          </a>
          <a href="/submit" className={navLink}>
            Submit
          </a>
          <a href="/moderation" className={navLink}>
            Moderation
          </a>
          <span className="mx-2 hidden h-5 w-px bg-[var(--border)] sm:inline" aria-hidden />
          <SiteAuthNav />
        </nav>
      </div>
    </header>
  );
}
