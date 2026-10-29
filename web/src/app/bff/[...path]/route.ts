import type { NextRequest } from "next/server";
import { API_URL, SESSION_COOKIE } from "@/lib/config";

// Thin pass-through to /api/v1. It turns the Ory cookie into the
// `Authorization: Session` header the backend expects and streams bodies both
// ways (multipart uploads in, SSE out). It makes no access decisions.

export const dynamic = "force-dynamic";

const PASS_REQ = ["content-type", "accept", "last-event-id"];
const PASS_RES = ["content-type", "cache-control", "content-disposition", "content-security-policy", "x-content-type-options"];

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const url = `${API_URL}/api/v1/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  for (const h of PASS_REQ) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  const session = req.cookies.get(SESSION_COOKIE)?.value;
  if (session) headers.set("authorization", `Session ${session}`);

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const upstream = await fetch(url, {
    method: req.method,
    headers,
    body: hasBody ? req.body : undefined,
    // Required by undici to stream a request body.
    ...(hasBody ? { duplex: "half" } : {}),
    signal: req.signal,
    cache: "no-store",
  } as RequestInit);

  const out = new Headers();
  for (const h of PASS_RES) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  if (out.get("content-type")?.startsWith("text/event-stream")) out.set("x-accel-buffering", "no");
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE };
