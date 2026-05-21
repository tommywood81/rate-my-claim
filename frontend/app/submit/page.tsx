"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { submitStatusMessage } from "@/lib/research-pipeline-ux";

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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitProgress, setSubmitProgress] = useState(0);
  const [submitStep, setSubmitStep] = useState(0);
  const [submitStartedAt, setSubmitStartedAt] = useState<number | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);

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

  useEffect(() => {
    if (!isSubmitting) return;
    const interval = setInterval(() => {
      setSubmitProgress((prev) => {
        const next = Math.min(prev + 6, 92);
        if (next >= 24) setSubmitStep(1);
        if (next >= 52) setSubmitStep(2);
        return next;
      });
    }, 240);
    return () => clearInterval(interval);
  }, [isSubmitting]);

  useEffect(() => {
    if (!isSubmitting || submitStartedAt === null) return;
    const interval = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - submitStartedAt) / 1000));
    }, 250);
    return () => clearInterval(interval);
  }, [isSubmitting, submitStartedAt]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    if (!csrfReady) {
      setMsg("Preparing secure session… try again in a moment.");
      return;
    }
    setIsSubmitting(true);
    setSubmitProgress(8);
    setSubmitStep(0);
    setSubmitStartedAt(Date.now());
    setElapsedSec(0);
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
        setSubmitStep(3);
        setSubmitProgress(100);
        try {
          sessionStorage.setItem("rmc_just_submitted_slug", data.public_slug);
        } catch {
          /* private mode */
        }
        router.push(`/claims/${encodeURIComponent(data.public_slug)}?submitted=1`);
        return;
      }
      setMsg(
        `Submission received (${data.id}). Open your claim page from Browse once processing links a public slug.`,
      );
      setText("");
      setUrls("");
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "Failed");
    } finally {
      setIsSubmitting(false);
      setSubmitProgress(0);
      setSubmitStep(0);
      setSubmitStartedAt(null);
      setElapsedSec(0);
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
          disabled={isSubmitting}
          required
          minLength={10}
          rows={6}
          className="owid-input w-full p-3 text-sm"
          placeholder="State one clear empirical claim…"
        />
        <textarea
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          disabled={isSubmitting}
          rows={4}
          className="owid-input w-full p-3 font-mono text-xs"
          placeholder="Optional source URLs, one per line"
        />
        <button
          type="submit"
          className="owid-btn-primary disabled:opacity-60"
          disabled={!csrfReady || isSubmitting}
        >
          {isSubmitting ? "Submitting..." : "Submit for enrichment"}
        </button>
        {isSubmitting && (
          <div className="space-y-2 rounded border border-[var(--border)] bg-[var(--bg-subtle)] p-3">
            <div className="flex items-center justify-between gap-3 text-xs text-[var(--muted)]">
              <div className="flex items-center gap-2">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[var(--accent)]" />
                <span>Working on your claim...</span>
              </div>
              <span>{elapsedSec}s</span>
            </div>
            <div
              className="h-2 overflow-hidden rounded bg-white"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={submitProgress}
              aria-label="Submission progress"
            >
              <div
                className="h-full bg-[var(--accent)] transition-all duration-300"
                style={{ width: `${submitProgress}%` }}
              />
            </div>
            <div className="h-1 w-full overflow-hidden rounded bg-white/70">
              <div className="h-full w-1/3 animate-pulse bg-[var(--accent)]/60" />
            </div>
            <p className="text-sm text-[var(--muted)]">{submitStatusMessage(elapsedSec, submitStep)}</p>
            <p className="text-xs text-[var(--muted)]">
              Next: the claim page will show live progress for the research agent (evidence) and
              decision agent (scores and verdict).
            </p>
          </div>
        )}
      </form>
      {msg && <p className="text-sm text-[var(--muted)]">{msg}</p>}
    </div>
  );
}
