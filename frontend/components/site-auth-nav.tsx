"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Me = { id: string; username: string; role: string };

export function SiteAuthNav() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetch("/api/v1/auth/me", { credentials: "include" });
      if (cancelled) return;
      if (res.status === 401 || res.status === 403 || !res.ok) {
        setMe(null);
        return;
      }
      const body = (await res.json()) as { success?: boolean; data?: Me };
      if (body.success && body.data?.id) {
        setMe({ id: body.data.id, username: body.data.username, role: body.data.role });
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

  const linkClass =
    "rounded px-2 py-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]";

  if (me === undefined) {
    return <span className="inline-block min-w-[4rem] text-xs text-[var(--muted)]">…</span>;
  }

  if (me === null) {
    return (
      <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
        <Link href="/login" className={`text-sm font-medium text-[var(--accent)] hover:underline ${linkClass}`}>
          Sign in
        </Link>
        <Link href="/register" className={`text-sm text-[var(--muted)] hover:text-[var(--fg)] ${linkClass}`}>
          Register
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-1 text-sm">
      <Link href={`/users/${me.id}`} className={`text-[var(--muted)] hover:text-[var(--fg)] ${linkClass}`}>
        <span className="font-medium text-[var(--fg)]">{me.username}</span>
        <span className="ml-1 text-xs">({me.role})</span>
      </Link>
      <button
        type="button"
        className={`text-[var(--accent)] underline-offset-2 hover:underline ${linkClass}`}
        onClick={logout}
      >
        Sign out
      </button>
    </div>
  );
}
