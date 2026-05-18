import type { Metadata } from "next";
import Link from "next/link";

import { serverGet } from "@/lib/api-server";
import type { UserProfile } from "@/lib/types";

export const dynamic = "force-dynamic";

async function loadUser(id: string): Promise<UserProfile | null> {
  return serverGet<UserProfile>(`/api/v1/users/${encodeURIComponent(id)}`, { cache: "no-store" });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const user = await loadUser(id);
  if (!user) return { title: "Profile" };
  return {
    title: `${user.username} · Profile`,
    description: `Public profile for ${user.username} on Rate My Claim.`,
  };
}

export default async function UserProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const user = await loadUser(id);

  if (!user) {
    return (
      <p className="text-sm text-[var(--muted)]" role="status">
        User not found.
      </p>
    );
  }

  const verified = Boolean(user.email_verified_at);

  return (
    <article className="max-w-xl space-y-6">
      <header className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">User profile</p>
        <h1 className="mt-1 text-2xl font-semibold">{user.username}</h1>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[var(--muted)]">Role</dt>
            <dd className="capitalize">{user.role}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Reputation</dt>
            <dd>{user.reputation_score.toFixed(1)}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Email verified</dt>
            <dd>{verified ? "Yes" : "No"}</dd>
          </div>
        </dl>
      </header>
      <p className="text-sm text-[var(--muted)]">
        <Link href="/claims" className="text-[var(--accent)] underline">
          Browse claims
        </Link>{" "}
        contributed to by this community member.
      </p>
    </article>
  );
}
