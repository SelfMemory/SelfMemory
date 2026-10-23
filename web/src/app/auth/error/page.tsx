import Link from "next/link";

export const metadata = { title: "Sign-in problem" };

export default function AuthError() {
  return (
    <main className="auth">
      <h1>That sign-in link has expired</h1>
      <p className="muted">Start again and it will work.</p>
      <Link className="btn" href="/auth/login">Sign in</Link>
    </main>
  );
}
