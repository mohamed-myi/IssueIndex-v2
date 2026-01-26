"use client";

import { PropsWithChildren, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";
import { useQuery } from "@tanstack/react-query";
import { fetchLanguages, fetchRepositories } from "@/lib/api/endpoints";
import { setQueryParam } from "@/lib/url";
import { cn } from "@/lib/cn";
import { TopNav } from "./TopNav";
import { FilterSidebar, type FilterState } from "./FilterSidebar";

const DEFAULT_LABELS = [
  "bug",
  "good first issue",
  "help wanted",
  "enhancement",
  "documentation",
  "performance",
  "security",
];

export function AppShell({
  activeTab,
  children,
}: PropsWithChildren<{ activeTab: "browse" | "dashboard" | "for-you" | null }>) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [sidebarOpen, setSidebarOpen] = useState(true);

  const filterState: FilterState = useMemo(
    () => ({
      language: searchParams.get("lang") ?? null,
      label: searchParams.get("label") ?? null,
      repo: searchParams.get("repo") ?? null,
    }),
    [searchParams],
  );

  function updateFilters(next: FilterState) {
    const url = new URL(pathname ?? "/", window.location.origin);
    url.search = searchParams.toString();

    setQueryParam(url, "lang", next.language);
    setQueryParam(url, "label", next.label);
    setQueryParam(url, "repo", next.repo);

    router.replace((url.pathname + url.search) as Route);
  }

  const languagesQuery = useQuery({
    queryKey: ["taxonomy", "languages"],
    queryFn: fetchLanguages,
    staleTime: 1000 * 60 * 30,
  });

  const reposQuery = useQuery({
    queryKey: ["repositories", "sidebar", filterState.language ?? "", ""],
    queryFn: () =>
      fetchRepositories({
        language: filterState.language ?? undefined,
        q: "",
        limit: 25,
      }),
    staleTime: 1000 * 60 * 10,
  });

  const languages = useMemo(() => languagesQuery.data?.languages ?? [], [languagesQuery.data]);
  const repos = useMemo(() => reposQuery.data?.repositories.map((r) => r.name) ?? [], [reposQuery.data]);

  return (
    <div className="min-h-screen">
      <TopNav activeTab={activeTab} sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen((v) => !v)} />
      <main className="pt-[var(--topnav-height)]">
        <div className="flex items-start">
          {/* Mobile Overlay */}
          <div
            className={cn(
              "fixed inset-0 z-40 bg-black/50 transition-opacity duration-300 md:hidden",
              sidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"
            )}
            onClick={() => setSidebarOpen(false)}
          />

          {/* Sidebar Container */}
          <div
            className={cn(
              // Base: Fixed for mobile, sticky for desktop
              "fixed bottom-0 left-0 top-[var(--topnav-height)] z-50 overflow-hidden transition-all duration-300 md:sticky md:top-[var(--topnav-height)] md:z-0 md:h-[calc(100vh-var(--topnav-height))]",
              // Mobile state: Translate X
              sidebarOpen ? "translate-x-0" : "-translate-x-full",
              // Desktop state: Always translate-0 (visibility controlled by width/margin of content if needed, but here we just slide it)
              "md:translate-x-0",
              // Desktop toggle: If we want to hide it on desktop, we usually shrink width. 
              // For this implementation, let's assume sidebarOpen affects desktop too (as per original design).
              // If closed on desktop, we hide it.
              !sidebarOpen && "md:hidden"
            )}
            style={{ width: "var(--sidebar-width)" }}
          >
            <FilterSidebar
              isVisible={true}
              languages={languages}
              labels={DEFAULT_LABELS}
              repos={repos}
              value={filterState}
              onChange={updateFilters}
            />
          </div>

          {/* Main Content */}
          <div
            className={cn(
              "min-w-0 flex-1 px-4 py-6 transition-all duration-300 md:px-8 md:py-8",
              // Desktop: Apply margin when sidebar is open, otherwise no margin
              sidebarOpen ? "md:ml-[var(--sidebar-width)]" : "md:ml-0"
            )}
            // We only apply margin on desktop if sidebar is open
            style={{
              marginLeft: 0 // Reset default
            }}
          >
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
