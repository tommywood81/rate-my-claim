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
        <p className="owid-kicker">Account</p>
        <h1 className="owid-page-heading text-3xl">Sign in</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Sign in to link submissions to your account and resubmit after revision requests.
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
