import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { KRATOS_URL } from "@/lib/config";

// Renders a Kratos browser flow (login or registration) as a plain form that
// posts straight to Kratos. Kratos owns validation, CSRF and the session
// cookie; this page only draws the nodes it returns.

type Node = {
  type: string;
  group: string;
  attributes: { name?: string; type?: string; value?: unknown; required?: boolean; autocomplete?: string; text?: { text: string } };
  messages: { id: number; text: string; type: string }[];
  meta: { label?: { text: string } };
};
type Flow = { id: string; ui: { action: string; method: string; nodes: Node[]; messages?: { id: number; text: string; type: string }[] } };

const LABELS: Record<string, string> = {
  identifier: "Email",
  "traits.email": "Email",
  "traits.name": "Name",
  password: "Password",
};
// Traits the backend assigns; people never type them.
const HIDDEN_TRAITS = new Set(["traits.organization_id", "traits.project_ids"]);

export async function KratosFlow({ type, params }: { type: "login" | "registration"; params: Record<string, string> }) {
  const { flow: id, return_to } = params;
  const start = `${KRATOS_URL}/self-service/${type}/browser${return_to ? `?return_to=${encodeURIComponent(return_to)}` : ""}`;
  if (!id) redirect(start);

  // Forward the raw Cookie header: Kratos checks its CSRF cookie byte for byte.
  const cookie = (await headers()).get("cookie") ?? "";
  const res = await fetch(`${KRATOS_URL}/self-service/${type}/flows?id=${encodeURIComponent(id)}`, {
    headers: { cookie, accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) redirect(start);
  const flow: Flow = await res.json();
  // Post to our own /api/auth/kratos proxy whatever host Kratos thinks it is on.
  const action = flow.ui.action.replace(/^https?:\/\/[^/]+(?=\/api\/auth\/kratos\/)/, "");
  const nodes = flow.ui.nodes.filter((n) => n.group !== "oidc" && n.type === "input");
  const messages = [...(flow.ui.messages ?? []), ...nodes.flatMap((n) => n.messages)];

  return (
    <main className="auth">
      <span className="brand">self<b>memory</b></span>
      <h1>{type === "login" ? "Sign in" : "Create your account"}</h1>
      {messages.map((m) => (
        <p key={m.id} className={m.type === "error" ? "error" : "muted"}>{m.text}</p>
      ))}
      <form action={action} method={flow.ui.method}>
        {nodes.map((n, i) => {
          const a = n.attributes;
          const name = a.name ?? "";
          if (a.type === "hidden" || HIDDEN_TRAITS.has(name)) {
            return HIDDEN_TRAITS.has(name) ? null : <input key={i} type="hidden" name={name} defaultValue={String(a.value ?? "")} />;
          }
          if (a.type === "submit" || a.type === "button") {
            return (
              <button key={i} className="btn" name={name} value={String(a.value ?? "")}>
                {submitLabel(type, n)}
              </button>
            );
          }
          return (
            <label key={i} className="field">
              {LABELS[name] ?? n.meta.label?.text ?? name}
              <input
                className="input"
                name={name}
                type={a.type}
                required={a.required}
                autoComplete={a.autocomplete}
                defaultValue={a.type === "password" ? undefined : String(a.value ?? "")}
              />
            </label>
          );
        })}
      </form>
      <p className="muted">
        {type === "login" ? (
          <>New here? <Link href="/auth/registration">Create an account</Link></>
        ) : (
          <>Already have an account? <Link href="/auth/login">Sign in</Link></>
        )}
      </p>
    </main>
  );
}

function submitLabel(type: string, n: Node) {
  if (n.attributes.value === "profile") return "Continue";
  if (n.attributes.value === "password") return type === "login" ? "Sign in" : "Create account";
  return n.meta.label?.text ?? "Continue";
}
