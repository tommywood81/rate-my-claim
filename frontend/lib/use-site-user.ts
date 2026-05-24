"use client";

import { useEffect, useState } from "react";

export type SiteUser = {
  id: string;
  username: string;
  role: string;
};

export function isStaffRole(role: string | undefined | null): boolean {
  return role === "moderator" || role === "admin";
}

/** Current session user from GET /api/v1/auth/me (undefined while loading). */
export function useSiteUser(): {
  user: SiteUser | null | undefined;
  isStaff: boolean;
} {
  const [user, setUser] = useState<SiteUser | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await fetch("/api/v1/auth/me", { credentials: "include" });
      if (cancelled) return;
      if (res.status === 401 || res.status === 403 || !res.ok) {
        setUser(null);
        return;
      }
      const body = (await res.json()) as { success?: boolean; data?: SiteUser };
      if (body.success && body.data?.id) {
        setUser(body.data);
      } else {
        setUser(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return {
    user,
    isStaff: user != null && isStaffRole(user.role),
  };
}
