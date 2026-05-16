"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Me = { username: string; role: string };

export function SiteAuthNav() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetch("/api/v1/auth/me", { credentials: "include" });
      if (cancelled) {
        return;
      }
      if (res.status === 401 || res.status === 403) {
        setMe(null);
        return;
      }
      if (!res.ok) {
        setMe(null);
        return;
      }
      const body = (await res.json()) as { success?: boolean; data?: Me };
      if (body.success && body.data) {
        setMe({ username: body.data.username, role: body.data.role });
      } else {
        setMe(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function logout() {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
    setMe(null);
    router.refresh();
  }

  if (me === undefined) {
    return <span className="inline-block min-w-[4rem] text-xs text-[var(--muted)]">…</span>;
  }

  if (me === null) {
    return (
      <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
        <Link href="/login" className="text-sm font-medium text-[var(--accent)] hover:underline">
          Sign in
        </Link>
        <Link href="/register" className="text-sm text-[var(--muted)] hover:text-[var(--fg)]">
          Register
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-1 text-sm">
      <span className="text-[var(--muted)]">
        <span className="font-medium text-[var(--fg)]">{me.username}</span>
        <span className="ml-1 text-xs">({me.role})</span>
      </span>
      <button
        type="button"
        className="text-[var(--accent)] underline-offset-2 hover:underline"
        onClick={logout}
      >
        Sign out
      </button>
    </div>
  );
}
