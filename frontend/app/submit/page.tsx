"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

type SubmitResponse = {
  id: string;
  public_slug?: string | null;
};

export default function SubmitPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [urls, setUrls] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [csrfReady, setCsrfReady] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        await apiFetch<Record<string, never>>("/api/v1/csrf");
        setCsrfReady(true);
      } catch {
        setCsrfReady(false);
      }
    })();
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (!csrfReady) {
      setMsg("Preparing secure session… try again in a moment.");
      return;
    }
    try {
      const list = urls
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      const data = await apiFetch<SubmitResponse>("/api/v1/pending-claims", {
        method: "POST",
        body: JSON.stringify({ raw_claim_text: text, source_urls: list }),
      });
      if (data.public_slug) {
        router.push(`/claims/${encodeURIComponent(data.public_slug)}`);
        return;
      }
      setMsg(
        `Submission received (${data.id}). Open your claim page from Browse once processing links a public slug.`,
      );
      setText("");
      setUrls("");
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <div className="max-w-2xl space-y-8">
      <header className="space-y-3 border-b border-[var(--border)] pb-6">
        <p className="owid-kicker">Contribute</p>
        <h1 className="owid-page-heading text-3xl">Submit a claim</h1>
      </header>
      <p className="owid-lead text-base">
        Anyone can submit. Your claim goes live immediately; research and evidence enrich the page in the background.
        Moderators refine claims over time rather than blocking publication.
      </p>
      <p className="owid-card px-4 py-3 text-sm text-[var(--muted)]">
        <span className="font-medium text-[var(--fg)]">Signed in?</span> Submissions are linked to your account so you
        can track status and resubmit after revision requests.{" "}
        <Link href="/login?next=/submit" className="text-[var(--accent)] hover:underline">
          Sign in
        </Link>{" "}
        or{" "}
        <Link href="/register" className="text-[var(--accent)] hover:underline">
          register
        </Link>
        .
      </p>
      <form onSubmit={onSubmit} className="space-y-4">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          required
          minLength={10}
          rows={6}
          className="owid-input w-full p-3 text-sm"
          placeholder="State one clear empirical claim…"
        />
        <textarea
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          rows={4}
          className="owid-input w-full p-3 font-mono text-xs"
          placeholder="Optional source URLs, one per line"
        />
        <button
          type="submit"
          className="owid-btn-primary disabled:opacity-60"
          disabled={!csrfReady}
        >
          Submit for enrichment
        </button>
      </form>
      {msg && <p className="text-sm text-[var(--muted)]">{msg}</p>}
    </div>
  );
}
