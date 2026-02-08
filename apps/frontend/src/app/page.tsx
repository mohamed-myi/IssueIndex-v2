"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import type { Route } from "next";
import { Search, Loader2 } from "lucide-react";
import { usePublicStats, useMe } from "@/lib/api/hooks";
import { logout } from "@/lib/api/endpoints";
import { useQueryClient } from "@tanstack/react-query";

const QUICK_TAGS = ["react", "typescript", "rust", "good first issue"];

export default function LandingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const statsQuery = usePublicStats();
  const meQuery = useMe();

  const isAuthenticated = meQuery.isSuccess;
  const isAuthLoading = meQuery.isLoading;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/browse?q=${encodeURIComponent(query.trim())}` as Route);
    } else {
      router.push("/browse" as Route);
    }
  }

  async function handleLogout() {
    setIsLoggingOut(true);
    try {
      await logout();
    } catch {
      // Cookie is cleared server-side regardless
    } finally {
      setIsLoggingOut(false);
      setShowLogoutConfirm(false);
      (window as unknown as { __HAS_SESSION__: boolean }).__HAS_SESSION__ = false;
      queryClient.removeQueries({ queryKey: ["auth"] });
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 sm:px-8 lg:px-12">
      {/* Main content - centered */}
      <div className="w-full max-w-xl flex flex-col items-center text-center">
        {/* Logo */}
        <div className="mb-8 sm:mb-10">
          <h1 className="text-2xl sm:text-3xl lg:text-4xl tracking-tight">
            <span className="font-extrabold text-foreground">ISSUE</span>
            <span className="font-light text-foreground/75">INDEX</span>
          </h1>
          <p
            className="mt-2 text-[14px] font-medium"
            style={{ color: "rgba(138, 144, 178, 1)" }}
          >
            Brought to you by MYI
          </p>
        </div>

        {/* Search bar */}
        <form onSubmit={handleSubmit} className="w-full mb-6">
          <div className="relative">
            {/* Focus glow effect */}
            {isFocused && (
              <div
                className="absolute -inset-1 rounded-2xl opacity-60"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(138, 92, 255, 0.25), rgba(99, 102, 241, 0.15))",
                  filter: "blur(16px)",
                }}
              />
            )}

            {/* Input container */}
            <div
              className="relative flex items-center gap-3 rounded-2xl px-5 py-4 transition-all duration-200"
              style={{
                backgroundColor: "rgba(17, 20, 32, 0.6)",
                border: `1px solid ${isFocused ? "rgba(138, 92, 255, 0.4)" : "rgba(255, 255, 255, 0.08)"}`,
              }}
            >
              <Search
                className="h-5 w-5 flex-shrink-0 transition-colors duration-200"
                style={{
                  color: isFocused
                    ? "rgba(138, 92, 255, 0.9)"
                    : "rgba(255, 255, 255, 0.35)",
                }}
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => setIsFocused(true)}
                onBlur={() => setIsFocused(false)}
                placeholder="Search issues..."
                className="flex-1 bg-transparent text-[15px] font-medium outline-none placeholder:text-white/30"
                style={{ color: "rgba(230, 233, 242, 0.95)" }}
              />
            </div>
          </div>
        </form>

        {/* Search examples */}
        <p
          className="text-[13px]"
          style={{ color: "rgba(138, 144, 178, 0.7)" }}
        >
          Try: {QUICK_TAGS.join(" · ")}
        </p>

        {/* CTA buttons */}
        <div className="mt-6 mb-8 flex flex-col items-center gap-3">
          {/* Browse Issues — always visible regardless of auth state */}
          <Link
            href={"/browse" as Route}
            className="btn-press btn-glow rounded-full px-5 py-2.5 text-[14px] font-semibold transition-all duration-200 hover:bg-white/10"
            style={{
              backgroundColor: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              color: "rgba(230, 233, 242, 0.95)",
            }}
          >
            Browse Issues
          </Link>

          {/* Auth-dependent buttons */}
          {isAuthenticated ? (
            showLogoutConfirm ? (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                  className="btn-press rounded-full px-4 py-2 text-[13px] font-semibold transition-all duration-200"
                  style={{
                    backgroundColor: "rgba(212, 24, 61, 0.15)",
                    border: "1px solid rgba(212, 24, 61, 0.3)",
                    color: "rgba(255, 120, 120, 0.95)",
                    opacity: isLoggingOut ? 0.7 : 1,
                  }}
                >
                  {isLoggingOut ? (
                    <span className="flex items-center gap-1.5">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Logging out…
                    </span>
                  ) : (
                    "Confirm"
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setShowLogoutConfirm(false)}
                  disabled={isLoggingOut}
                  className="btn-press rounded-full px-4 py-2 text-[13px] font-semibold transition-all duration-200 hover:bg-white/10"
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.05)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    color: "rgba(230, 233, 242, 0.7)",
                  }}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowLogoutConfirm(true)}
                className="btn-press btn-glow rounded-full px-5 py-2.5 text-[13px] font-semibold transition-all duration-200 hover:bg-white/10"
                style={{
                  backgroundColor: "rgba(138, 92, 255, 0.12)",
                  border: "1px solid rgba(138, 92, 255, 0.25)",
                  color: "rgba(200, 190, 255, 0.95)",
                }}
              >
                Log out
              </button>
            )
          ) : !isAuthLoading ? (
            <Link
              href="/login"
              className="btn-press btn-glow rounded-full px-5 py-2.5 text-[13px] font-semibold transition-all duration-200 hover:bg-white/10"
              style={{
                backgroundColor: "rgba(138, 92, 255, 0.12)",
                border: "1px solid rgba(138, 92, 255, 0.25)",
                color: "rgba(200, 190, 255, 0.95)",
              }}
            >
              Sign In
            </Link>
          ) : null}
        </div>
      </div>

      {/* Bottom section - Learn more, Stats */}
      <div className="absolute bottom-0 left-0 right-0 pb-8 px-6">
        <div className="max-w-xl mx-auto flex flex-col items-center">
          {/* Learn More link */}
          <Link
            href="/docs"
            className="btn-press mb-6 text-[13px] font-medium underline underline-offset-2 transition-colors duration-200 hover:text-white"
            style={{ color: "rgba(138, 144, 178, 0.8)" }}
          >
            Learn More
          </Link>

          {/* Separator */}
          <div
            className="w-full h-px mb-4"
            style={{ backgroundColor: "rgba(255, 255, 255, 0.06)" }}
          />

          {/* Stats line */}
          <p
            className="text-center text-[13px]"
            style={{ color: "rgba(138, 144, 178, 0.6)" }}
          >
            {statsQuery.data ? (
              <>
                {statsQuery.data.total_issues?.toLocaleString() ?? "\u2014"} issues
                {" \u00B7 "}
                {statsQuery.data.total_repos?.toLocaleString() ?? "\u2014"} repos
                {" \u00B7 "}
                {statsQuery.data.total_languages ?? "\u2014"} languages indexed
              </>
            ) : (
              "Loading stats..."
            )}
          </p>
        </div>
      </div>
    </main>
  );
}
