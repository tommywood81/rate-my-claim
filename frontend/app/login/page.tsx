import Link from "next/link";

import { LoginForm } from "./login-form";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; registered?: string }>;
}) {
  const sp = await searchParams;
  const next = sp.next?.startsWith("/") ? sp.next : undefined;
  const registered = sp.registered === "1";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Use a moderator or admin account for moderation and generating AI analysis on claims. Session uses secure
          cookies on this site.
        </p>
      </div>
      {registered && (
        <p className="rounded border border-green-700/30 bg-green-50 px-3 py-2 text-sm text-green-900">
          Account created. Sign in with your new username and password.
        </p>
      )}
      <LoginForm defaultNext={next} />
      <p className="text-center text-sm">
        <Link href="/" className="text-[var(--muted)] hover:text-[var(--fg)]">
          ← Back to home
        </Link>
      </p>
    </div>
  );
}
