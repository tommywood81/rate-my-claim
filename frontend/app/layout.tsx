import type { Metadata } from "next";

import { SiteHeader } from "@/components/site-header";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: {
    default: "Rate My Claim",
    template: "%s · Rate My Claim",
  },
  description: "Evidence-backed semantic claim intelligence platform",
  metadataBase: process.env.NEXT_PUBLIC_SITE_URL
    ? new URL(process.env.NEXT_PUBLIC_SITE_URL)
    : undefined,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <SiteHeader />
          <main id="main-content" className="mx-auto max-w-5xl px-4 py-8" tabIndex={-1}>
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
