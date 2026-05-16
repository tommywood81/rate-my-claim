"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { messageFromApiBody } from "@/lib/api-errors";

export function RegisterForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/register", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
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
        throw new Error(messageFromApiBody(body, "Registration failed"));
      }
      router.push("/login?registered=1");
      router.refresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="mx-auto max-w-md space-y-4 rounded border border-[var(--border)] bg-[var(--card)] p-6"
    >
      <div>
        <label htmlFor="reg-username" className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Username
        </label>
        <input
          id="reg-username"
          name="username"
          autoComplete="username"
          required
          minLength={3}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2"
        />
      </div>
      <div>
        <label htmlFor="reg-email" className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Email
        </label>
        <input
          id="reg-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2"
        />
      </div>
      <div>
        <label htmlFor="reg-password" className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Password
        </label>
        <input
          id="reg-password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded border border-[var(--border)] px-3 py-2"
        />
        <p className="mt-1 text-xs text-[var(--muted)]">At least 10 characters.</p>
      </div>
      {err && <p className="text-sm text-red-700">{err}</p>}
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white enabled:hover:opacity-95 disabled:opacity-60"
      >
        {loading ? "Creating account…" : "Create account"}
      </button>
      <p className="text-center text-sm text-[var(--muted)]">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-[var(--accent)] hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
