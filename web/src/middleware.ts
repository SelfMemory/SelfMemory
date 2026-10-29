import { NextResponse, type NextRequest } from "next/server";
import { KRATOS_URL, SESSION_COOKIE } from "@/lib/config";

// Redirects only. Whether the session is valid, and what it may read, is the
// backend's call on every request.
export function middleware(req: NextRequest) {
  if (req.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const login = new URL(`${KRATOS_URL}/self-service/login/browser`);
  login.searchParams.set("return_to", req.nextUrl.href);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!bff|auth|api/auth|_next|favicon.ico).*)"],
};
