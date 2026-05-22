"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { logoutSession } from "@/lib/api";

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
    try {
      await logoutSession();
    } catch {
      /* still clear local UI; server may already be logged out */
    }
    setMe(null);
    router.replace("/");
    router.refresh();
  }

  const linkClass =
    "owid-nav-link focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]";

  if (me === undefined) {
    return <span className="inline-block min-w-[4rem] text-xs text-[var(--muted)]">…</span>;
  }

  if (me === null) {
    return (
      <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-1">
        <Link href="/login" className={`${linkClass} font-semibold text-[var(--accent-dark)]`}>
          Sign in
        </Link>
        <Link href="/register" className={linkClass}>
          Register
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-1 text-sm">
      <Link href={`/users/${me.id}`} className={linkClass}>
        <span className="font-medium text-[var(--fg)]">{me.username}</span>
        <span className="ml-1 text-xs text-[var(--muted)]">({me.role})</span>
      </Link>
      <button type="button" className={`${linkClass} cursor-pointer bg-transparent`} onClick={logout}>
        Sign out
      </button>
    </div>
  );
}
