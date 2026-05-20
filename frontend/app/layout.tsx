import type { Metadata } from "next";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { bodyFont, displayFont } from "@/app/fonts";

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
    <html lang="en" className={`${bodyFont.variable} ${displayFont.variable}`}>
      <body className="min-h-screen flex flex-col">
        <Providers>
          <SiteHeader />
          <main id="main-content" className="mx-auto w-full max-w-content flex-1 px-4 py-8 sm:px-6" tabIndex={-1}>
            {children}
          </main>
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
