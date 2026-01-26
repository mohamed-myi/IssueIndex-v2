import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that require authentication
const PROTECTED_ROUTES = [
    "/dashboard",
    "/profile",
    "/saved",
    "/for-you",
    "/auth/link",
    "/auth/connect",
];

// Routes that are public but might behave differently when logged in (e.g. login page)
const AUTH_ROUTES = ["/login"];

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Check for session cookie
    // The backend sets 'session_id'
    const sessionId = request.cookies.get("session_id")?.value;
    const isAuthenticated = !!sessionId;

    // 1. Protect private routes
    if (PROTECTED_ROUTES.some((route) => pathname.startsWith(route))) {
        if (!isAuthenticated) {
            const loginUrl = new URL("/login", request.url);
            loginUrl.searchParams.set("from", pathname); // Optional: remember where they were
            return NextResponse.redirect(loginUrl);
        }
    }

    // 2. Redirect authenticated users away from login page
    if (AUTH_ROUTES.some((route) => pathname.startsWith(route))) {
        if (isAuthenticated) {
            return NextResponse.redirect(new URL("/dashboard", request.url));
        }
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
