"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

export default function SubmitPage() {
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
      const data = await apiFetch<{ id: string }>("/api/v1/pending-claims", {
        method: "POST",
        body: JSON.stringify({ raw_claim_text: text, source_urls: list }),
      });
      setMsg(
        `Queued submission ${data.id}. It enters the moderation queue after background enrichment. ` +
          `Sign in to link submissions to your account and resubmit after revision requests.`,
      );
      setText("");
      setUrls("");
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold">Submit a claim</h1>
      <p className="text-sm text-[var(--muted)]">
        Anyone can submit. Claims should be atomic, empirical, and falsifiable. Optional URLs are fetched during
        enrichment for structured citations.
      </p>
      <p className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--muted)]">
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
          className="w-full rounded border border-[var(--border)] p-3 text-sm"
          placeholder="State one clear empirical claim…"
        />
        <textarea
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          rows={4}
          className="w-full rounded border border-[var(--border)] p-3 font-mono text-xs"
          placeholder="Optional source URLs, one per line"
        />
        <button
          type="submit"
          className="rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-95 disabled:opacity-60"
          disabled={!csrfReady}
        >
          Submit for enrichment
        </button>
      </form>
      {msg && <p className="text-sm text-[var(--muted)]">{msg}</p>}
    </div>
  );
}
