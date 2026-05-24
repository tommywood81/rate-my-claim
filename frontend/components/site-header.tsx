"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { SiteAuthNav } from "@/components/site-auth-nav";
import { useSiteUser } from "@/lib/use-site-user";

type NavItem = {
  href: string;
  label: string;
  match: (pathname: string) => boolean;
  staffOnly?: boolean;
};

const NAV: NavItem[] = [
  {
    href: "/claims",
    label: "Browse",
    match: (p) => p === "/claims" || p.startsWith("/claims/"),
  },
  {
    href: "/search",
    label: "Search",
    match: (p) => p === "/search" || p.startsWith("/search/"),
  },
  {
    href: "/atlas",
    label: "Claim map",
    match: (p) => p === "/atlas" || p.startsWith("/atlas/"),
  },
  {
    href: "/submit",
    label: "Submit",
    match: (p) => p === "/submit" || p.startsWith("/submit/"),
  },
  {
    href: "/moderation",
    label: "Maintenance",
    match: (p) => p === "/moderation" || p.startsWith("/moderation/"),
    staffOnly: true,
  },
];

function navClass(active: boolean): string {
  return active ? "owid-nav-link owid-nav-link-active" : "owid-nav-link";
}

export function SiteHeader() {
  const pathname = usePathname() ?? "";
  const { isStaff } = useSiteUser();
  const items = NAV.filter((item) => !item.staffOnly || isStaff);

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-white/95 backdrop-blur-sm">
      <a
        href="#main-content"
        className="skip-link absolute left-2 top-2 z-50 -translate-y-16 rounded-sm bg-[var(--accent-dark)] px-3 py-2 text-sm text-white focus:translate-y-0"
      >
        Skip to main content
      </a>
      <div className="mx-auto flex max-w-content items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link
          href="/"
          className="owid-display text-xl text-[var(--accent-dark)] no-underline hover:text-[var(--accent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          Rate My Claim
        </Link>
        <nav className="flex flex-1 flex-wrap items-center justify-end gap-0.5 sm:gap-1" aria-label="Primary">
          {items.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={navClass(active)}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
          <span className="mx-2 hidden h-5 w-px bg-[var(--border)] sm:inline" aria-hidden />
          <SiteAuthNav />
        </nav>
      </div>
    </header>
  );
}
