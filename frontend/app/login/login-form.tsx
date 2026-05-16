"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { messageFromApiBody } from "@/lib/api-errors";

type Props = { defaultNext?: string };

export function LoginForm({ defaultNext }: Props) {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      let body: unknown = {};
      try {
        body = await res.json();
      } catch {
        body = {};
      }
      if (!res.ok) {
        throw new Error(messageFromApiBody(body, res.statusText));
      }
      const rec = body as { success?: boolean };
      if (rec.success === false) {
        throw new Error(messageFromApiBody(body, "Login failed"));
      }
      const next = defaultNext?.startsWith("/") ? defaultNext : "/";
      router.push(next);
      router.refresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-md space-y-4 rounded border border-[var(--border)] bg-[var(--card)] p-6">
      <div>
        <label htmlFor="username" className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Username
        </label>
        <input
          id="username"
          name="username"
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2"
        />
      </div>
      <div>
        <label htmlFor="password" className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2"
        />
      </div>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white enabled:hover:opacity-95 disabled:opacity-60"
      >
        {loading ? "Signing in…" : "Sign in"}
      </button>
      <p className="text-center text-sm text-[var(--muted)]">
        No account?{" "}
        <Link href="/register" className="font-medium text-[var(--accent)] hover:underline">
          Register
        </Link>
      </p>
    </form>
  );
}
