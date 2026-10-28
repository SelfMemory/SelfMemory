import type { NextRequest } from "next/server";
import { KRATOS_URL } from "@/lib/config";

// Same-origin pass-through to Kratos's public API, at the path Kratos's
// serve.public.base_url points to (as the old dashboard did). Keeps the
// session and CSRF cookies first-party. Redirects are returned, not followed.

export const dynamic = "force-dynamic";

const PASS_REQ = ["cookie", "content-type", "accept", "x-session-token", "x-csrf-token"];

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const headers = new Headers();
  for (const h of PASS_REQ) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  headers.set("x-forwarded-host", req.headers.get("host") ?? "");
  headers.set("x-forwarded-proto", req.nextUrl.protocol.replace(":", ""));
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const upstream = await fetch(`${KRATOS_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`, {
    method: req.method,
    headers,
    body: hasBody ? await req.arrayBuffer() : undefined,
    redirect: "manual",
    cache: "no-store",
  });
  const out = new Headers();
  for (const [k, v] of upstream.headers) {
    if (!["content-encoding", "content-length", "transfer-encoding", "connection"].includes(k)) out.append(k, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
