import Link from "next/link";

import { RegisterForm } from "./register-form";

export default function RegisterPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="owid-kicker">Account</p>
        <h1 className="owid-page-heading text-3xl">Create an account</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          New accounts are standard users. Moderator access is assigned separately. After registering, sign in from
          the login page.
        </p>
      </div>
      <RegisterForm />
      <p className="text-center text-sm">
        <Link href="/" className="text-[var(--muted)] hover:text-[var(--fg)]">
          ← Back to home
        </Link>
      </p>
    </div>
  );
}
