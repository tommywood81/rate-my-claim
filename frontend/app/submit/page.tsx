"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { SubmitPipelineProgress } from "@/components/submit-pipeline-progress";
import { apiFetch } from "@/lib/api";
import {
  PIPELINE_TERMINAL,
  isPipelineInFlight,
  submitStatusMessage,
} from "@/lib/research-pipeline-ux";
import type { ClaimDetail } from "@/lib/types";

type SubmitResponse = {
  id: string;
  public_slug?: string | null;
  processing_status?: string;
  canonical_candidate_text?: string | null;
  ai_summary?: string | null;
  duplicate_candidate_ids?: string[] | null;
  duplicate_hints?: { id: string; slug?: string | null; title?: string | null }[] | null;
  source_urls?: string[] | null;
  error_message?: string | null;
};

type TrackingState = {
  pendingId: string;
  slug: string;
  sourceUrlCount: number;
  duplicateCount: number;
  canonicalCandidate: string | null;
  errorMessage: string | null;
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
  const [tracking, setTracking] = useState<TrackingState | null>(null);
  const [claimDetail, setClaimDetail] = useState<ClaimDetail | null>(null);
  const [indexedClaims, setIndexedClaims] = useState<number | undefined>(undefined);
  const [autoRedirectSec, setAutoRedirectSec] = useState<number | null>(null);
  const trackStartedAt = useRef<number | null>(null);

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
    if (!isSubmitting && !tracking) return;
    const start = tracking ? trackStartedAt.current : submitStartedAt;
    if (start == null) return;
    const interval = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - start) / 1000));
    }, 250);
    return () => clearInterval(interval);
  }, [isSubmitting, tracking, submitStartedAt]);

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

  const pollClaim = useCallback(async (slug: string) => {
    const res = await fetch(`/api/v1/claims/${encodeURIComponent(slug)}`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { data?: ClaimDetail };
    return body.data ?? null;
  }, []);

  useEffect(() => {
    if (!tracking?.slug) return;

    let cancelled = false;

    void (async () => {
      try {
        const atlasRes = await fetch("/api/v1/atlas/claims", { cache: "no-store" });
        if (atlasRes.ok) {
          const atlasBody = (await atlasRes.json()) as { data?: { total_indexed?: number } };
          if (!cancelled && atlasBody.data?.total_indexed != null) {
            setIndexedClaims(atlasBody.data.total_indexed);
          }
        }
      } catch {
        /* optional */
      }
    })();

    const tick = async () => {
      try {
        const detail = await pollClaim(tracking.slug);
        if (cancelled || !detail) return;
        setClaimDetail(detail);
        if (PIPELINE_TERMINAL.has(detail.processing_status ?? "")) {
          if (detail.processing_status === "awaiting_moderation" || detail.processing_status === "completed") {
            setAutoRedirectSec(4);
          }
        }
      } catch {
        /* keep polling */
      }
    };

    void tick();
    const interval = setInterval(() => void tick(), 2800);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [tracking?.slug, pollClaim]);

  useEffect(() => {
    if (autoRedirectSec == null || !tracking?.slug) return;
    if (autoRedirectSec <= 0) {
      try {
        sessionStorage.setItem("rmc_just_submitted_slug", tracking.slug);
      } catch {
        /* private mode */
      }
      router.push(`/claims/${encodeURIComponent(tracking.slug)}?submitted=1`);
      return;
    }
    const t = setTimeout(() => setAutoRedirectSec((s) => (s != null ? s - 1 : null)), 1000);
    return () => clearTimeout(t);
  }, [autoRedirectSec, tracking?.slug, router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    setTracking(null);
    setClaimDetail(null);
    setAutoRedirectSec(null);
    if (!csrfReady) {
      setMsg("Preparing secure session… try again in a moment.");
      return;
    }
    setIsSubmitting(true);
    setSubmitProgress(8);
    setSubmitStep(0);
    setSubmitStartedAt(Date.now());
    setElapsedSec(0);
    let startedTracking = false;
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
        startedTracking = true;
        setSubmitProgress(100);
        setSubmitStep(3);
        trackStartedAt.current = Date.now();
        setElapsedSec(0);
        setTracking({
          pendingId: data.id,
          slug: data.public_slug,
          sourceUrlCount: list.length,
          duplicateCount: data.duplicate_hints?.length ?? data.duplicate_candidate_ids?.length ?? 0,
          canonicalCandidate: data.canonical_candidate_text ?? null,
          errorMessage: data.error_message ?? null,
        });
        try {
          sessionStorage.setItem("rmc_just_submitted_slug", data.public_slug);
        } catch {
          /* private mode */
        }
        const initial = await pollClaim(data.public_slug);
        if (initial) setClaimDetail(initial);
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
      if (!startedTracking) {
        setSubmitProgress(0);
        setSubmitStep(0);
        setSubmitStartedAt(null);
      }
    }
  }

  const processingStatus = claimDetail?.processing_status ?? (tracking ? "submitted" : null);
  const inFlight = isPipelineInFlight(processingStatus);

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

      {tracking && (
        <SubmitPipelineProgress
          slug={tracking.slug}
          processingStatus={processingStatus}
          pipelineStageKey={claimDetail?.pipeline_stage_key}
          claimDetail={claimDetail}
          elapsedSec={elapsedSec}
          trackCtx={{
            elapsedSec,
            sourceUrlCount: tracking.sourceUrlCount,
            indexedClaims,
          }}
          duplicateCount={tracking.duplicateCount}
          canonicalCandidate={tracking.canonicalCandidate}
          errorMessage={tracking.errorMessage}
          autoRedirectSec={inFlight ? null : autoRedirectSec}
        />
      )}

      {!tracking && (
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
                  <span>Sending your claim…</span>
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
              <p className="text-sm text-[var(--muted)]">{submitStatusMessage(elapsedSec, submitStep)}</p>
            </div>
          )}
        </form>
      )}

      {tracking && (
        <p className="text-sm text-[var(--muted)]">
          <button
            type="button"
            className="text-[var(--accent)] hover:underline"
            onClick={() => {
              setTracking(null);
              setClaimDetail(null);
              setAutoRedirectSec(null);
              setText("");
              setUrls("");
            }}
          >
            Submit another claim
          </button>
        </p>
      )}

      {msg && <p className="text-sm text-[var(--muted)]">{msg}</p>}
    </div>
  );
}
