import type { Metadata } from "next";

import { SiteAuthNav } from "@/components/site-auth-nav";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Rate My Claim",
  description: "Evidence-backed semantic claim intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <header className="border-b border-[var(--border)] bg-[var(--card)]">
            <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
              <a href="/" className="text-lg font-semibold tracking-tight text-[var(--accent)]">
                Rate My Claim
              </a>
              <nav className="flex flex-1 flex-wrap items-center gap-4 text-sm text-[var(--muted)]">
                <a href="/claims">Browse</a>
                <a href="/submit">Submit</a>
                <a href="/moderation">Moderation</a>
                <span className="hidden sm:inline sm:flex-1" aria-hidden />
                <SiteAuthNav />
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
