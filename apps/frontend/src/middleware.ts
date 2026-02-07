/**
 * Note (prod / *.run.app):
 * I can't check auth here using the `session_id` cookie because the backend sets it on the API host
 * (issueindex-api-*.a.run.app) and host-only cookies are not visible on the frontend host
 * (issueindex-frontend-*.a.run.app). This caused an infinite redirect back to /login after successful OAuth.
 *
 * Temporary approach: do auth gating client-side by calling GET /auth/me. Redirect to /login only if /auth/me returns 401.
 * See lib/hooks/use-auth-guard.ts.
 *
 * To revert: switch to a custom domain.
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(_request: NextRequest) {
  // All auth gating is now handled client-side via useAuthGuard().
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
