/**
 * Server-side auth gating via session_id cookie presence.
 *
 * Now that frontend (issueindex.dev) and API (api.issueindex.dev) share a
 * cookie domain (.issueindex.dev), the session_id cookie is visible here.
 *
 * This is a fast-path check only (cookie presence, not validity).
 * The useAuthGuard hook still validates the session against the API as a
 * secondary check to catch expired/revoked sessions.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "session_id";

/** Paths that require authentication. */
const PROTECTED_PREFIXES = ["/dashboard", "/for-you", "/saved", "/profile", "/settings"];

/** Paths that authenticated users should be redirected away from. */
const AUTH_PAGE = "/login";

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);

  // Redirect unauthenticated users away from protected pages
  if (isProtected(pathname) && !hasSession) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    return NextResponse.redirect(loginUrl);
  }

  // Redirect authenticated users away from the login page
  if (pathname === AUTH_PAGE && hasSession) {
    const dashboardUrl = request.nextUrl.clone();
    dashboardUrl.pathname = "/dashboard";
    return NextResponse.redirect(dashboardUrl);
  }

  return NextResponse.next();
}

// Configure which paths the middleware runs on
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (metadata files)
     * - public files (images, etc)
     */
    "/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
