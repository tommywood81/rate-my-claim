"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Pending = {
  id: string;
  raw_claim_text: string;
  processing_status: string;
  created_at: string;
};

export default function ModerationPage() {
  const [rows, setRows] = useState<Pending[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await apiFetch<Pending[]>("/api/v1/moderation/pending-claims?limit=30");
        setRows(data);
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : "Failed to load queue (moderator login required)");
      }
    })();
  }, []);

  async function act(id: string, action: "approve_claim" | "reject_claim") {
    setErr(null);
    try {
      await apiFetch("/api/v1/moderation/actions", {
        method: "POST",
        body: JSON.stringify({
          action_type: action,
          target_type: "pending_claim",
          target_id: id,
          explanation: action === "approve_claim" ? "Approved via UI" : "Rejected via UI",
        }),
      });
      setRows((r) => r.filter((x) => x.id !== id));
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Action failed");
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Moderation queue</h1>
      <p className="text-sm text-[var(--muted)]">
        Requires a moderator or admin account. Sign in via API <code>/api/v1/auth/login</code> (cookies) from the
        same browser origin.
      </p>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <ul className="divide-y divide-[var(--border)] rounded border border-[var(--border)] bg-[var(--card)]">
        {rows.map((p) => (
          <li key={p.id} className="space-y-2 px-4 py-3">
            <p className="text-xs text-[var(--muted)]">
              {p.id} · {p.processing_status} · {new Date(p.created_at).toLocaleString()}
            </p>
            <p className="text-sm">{p.raw_claim_text}</p>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded border border-[var(--border)] px-3 py-1 text-xs"
                onClick={() => act(p.id, "approve_claim")}
              >
                Approve
              </button>
              <button
                type="button"
                className="rounded border border-[var(--border)] px-3 py-1 text-xs"
                onClick={() => act(p.id, "reject_claim")}
              >
                Reject
              </button>
            </div>
          </li>
        ))}
        {rows.length === 0 && !err && <li className="px-4 py-6 text-sm text-[var(--muted)]">Queue empty.</li>}
      </ul>
    </div>
  );
}
