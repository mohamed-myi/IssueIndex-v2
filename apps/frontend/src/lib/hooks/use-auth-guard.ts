"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import { useMe } from "@/lib/api/hooks";

function is401(err: unknown): boolean {
  return axios.isAxiosError(err) && err.response?.status === 401;
}

/**
 * Client-side auth guard. Calls GET /auth/me and redirects to /login on 401.
 *
 * Use this on every page that requires authentication, since the Next.js
 * middleware cannot enforce auth via `session_id` cookie when the API and
 * frontend run on different Cloud Run hosts.
 *
 * @see middleware.ts for full explanation
 */
export function useAuthGuard() {
  const router = useRouter();
  const meQuery = useMe();

  useEffect(() => {
    if (meQuery.isError && is401(meQuery.error)) {
      router.replace("/login");
    }
  }, [meQuery.isError, meQuery.error, router]);

  return {
    /** true while /auth/me is still in progress */
    isLoading: meQuery.isLoading,
    /** true once /auth/me succeeded */
    isAuthenticated: meQuery.isSuccess,
    /** true once /auth/me returned 401 (redirect is in progress) */
    isRedirecting: meQuery.isError && is401(meQuery.error),
    /** the raw React Query result (access .data for user info) */
    me: meQuery,
  };
}
