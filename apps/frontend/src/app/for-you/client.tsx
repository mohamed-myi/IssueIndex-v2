"use client";

import type { Route } from "next";
import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/common/EmptyState";
import { SkeletonList } from "@/components/common/SkeletonList";
import { IssueListItem, type IssueListItemModel } from "@/components/issues/IssueListItem";
import { IssueDetailPanel, type IssueDetailModel } from "@/components/issues/IssueDetailPanel";
import { ProfileCTA } from "@/components/issues/ProfileCTA";
import { getApiErrorMessage } from "@/lib/api/client";
import {
  useSearch,
  useFeed,
  useBookmarkCheck,
  useCreateBookmark,
  useDeleteBookmark,
  useLogRecommendationEvents,
  useLogSearchInteraction,
} from "@/lib/api/hooks";
import { useAuthGuard } from "@/lib/hooks/use-auth-guard";
import { useInfiniteScroll } from "@/lib/hooks/use-infinite-scroll";

export default function ForYouClient() {
  const sp = useSearchParams();
  const router = useRouter();

  const q = sp.get("q") ?? "";
  const lang = sp.get("lang") ?? null;
  const label = sp.get("label") ?? null;
  const repo = sp.get("repo") ?? null;

  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);

  const { me: meQuery, isRedirecting } = useAuthGuard();

  const filters = useMemo(
    () => ({
      languages: lang ? [lang] : undefined,
      labels: label ? [label] : undefined,
      repos: repo ? [repo] : undefined,
    }),
    [lang, label, repo]
  );

  const searchQuery = useSearch({
    query: q,
    filters,
    pageSize: 20,
    enabled: q.trim().length > 0,
  });

  const feedQuery = useFeed(20, filters);
  const logRecommendationEvents = useLogRecommendationEvents();
  const logSearchInteraction = useLogSearchInteraction();
  const loggedRecommendationBatchIds = useRef<Set<string>>(new Set());

  const activeQuery = q.trim().length > 0 ? searchQuery : feedQuery;

  const searchContextByNodeId = useMemo(() => {
    const map = new Map<string, { searchId: string; position: number }>();
    if (q.trim().length === 0) return map;
    const pages = searchQuery.data?.pages ?? [];
    for (const page of pages) {
      for (const [idx, result] of page.results.entries()) {
        map.set(result.node_id, {
          searchId: page.search_id,
          position: (page.page - 1) * page.page_size + idx + 1,
        });
      }
    }
    return map;
  }, [q, searchQuery.data]);

  const recommendationContextByNodeId = useMemo(() => {
    const map = new Map<string, { recommendationBatchId: string; position: number }>();
    const pages = feedQuery.data?.pages ?? [];
    for (const page of pages) {
      if (!page.recommendation_batch_id) continue;
      for (const [idx, result] of page.results.entries()) {
        map.set(result.node_id, {
          recommendationBatchId: page.recommendation_batch_id,
          position: idx + 1,
        });
      }
    }
    return map;
  }, [feedQuery.data]);

  useEffect(() => {
    if (q.trim().length > 0) return;

    const pages = feedQuery.data?.pages ?? [];
    for (const page of pages) {
      const batchId = page.recommendation_batch_id;
      if (!batchId || loggedRecommendationBatchIds.current.has(batchId)) {
        continue;
      }

      const events = page.results.map((result, idx) => ({
        event_id: crypto.randomUUID(),
        event_type: "impression" as const,
        issue_node_id: result.node_id,
        position: idx + 1,
        surface: "for-you",
      }));
      if (events.length === 0) continue;

      loggedRecommendationBatchIds.current.add(batchId);
      logRecommendationEvents.mutate(
        {
          recommendation_batch_id: batchId,
          events,
        },
        {
          onError: () => {
            loggedRecommendationBatchIds.current.delete(batchId);
          },
        },
      );
    }
  }, [q, feedQuery.data, logRecommendationEvents]);

  const items = useMemo(() => {
    if (q.trim().length > 0) {
      const searchPages = searchQuery.data?.pages ?? [];
      const allResults = searchPages.flatMap((page) => page.results);
      return allResults.map<IssueListItemModel>((r) => ({
        nodeId: r.node_id,
        title: r.title,
        repoName: r.repo_name,
        primaryLanguage: r.primary_language,
        labels: r.labels,
        qScore: r.q_score,
        createdAt: r.github_created_at,
        bodyPreview: r.body_preview,
        whyThis: null,
        githubUrl: r.github_url ?? null,
      }));
    }

    const feedPages = feedQuery.data?.pages ?? [];
    const allResults = feedPages.flatMap((page) => page.results);
    return allResults.map<IssueListItemModel>((r) => ({
      nodeId: r.node_id,
      title: r.title,
      repoName: r.repo_name,
      primaryLanguage: r.primary_language,
      labels: r.labels,
      qScore: r.q_score,
      createdAt: r.github_created_at,
      bodyPreview: r.body_preview,
      whyThis: r.why_this ?? null,
      githubUrl: r.github_url ?? null,
    }));
  }, [q, searchQuery.data, feedQuery.data]);

  // Bookmark handling
  const issueNodeIds = useMemo(() => items.map((i) => i.nodeId), [items]);
  const bookmarkCheckQuery = useBookmarkCheck(issueNodeIds);
  const createBookmark = useCreateBookmark();
  const deleteBookmarkMutation = useDeleteBookmark();

  const bookmarksMap = useMemo(
    () => bookmarkCheckQuery.data?.bookmarks ?? {},
    [bookmarkCheckQuery.data?.bookmarks],
  );

  const handleToggleBookmark = useCallback(
    (issue: IssueListItemModel) => {
      const bookmarkId = bookmarksMap[issue.nodeId];
      if (bookmarkId) {
        deleteBookmarkMutation.mutate(bookmarkId);
      } else {
        createBookmark.mutate({
          issue_node_id: issue.nodeId,
          github_url: issue.githubUrl ?? `https://github.com/${issue.repoName}`,
          title_snapshot: issue.title,
          body_snapshot: issue.bodyPreview ?? "",
        });
      }
    },
    [bookmarksMap, createBookmark, deleteBookmarkMutation],
  );

  // Selected issue for detail panel
  const selectedIssue = useMemo(() => {
    if (!selectedIssueId) return null;
    const found = items.find((i) => i.nodeId === selectedIssueId);
    if (!found) return null;
    return {
      nodeId: found.nodeId,
      title: found.title,
      repoName: found.repoName,
      primaryLanguage: found.primaryLanguage,
      labels: found.labels,
      qScore: found.qScore,
      bodyPreview: found.bodyPreview,
      githubUrl: found.githubUrl ?? undefined,
    } as IssueDetailModel;
  }, [selectedIssueId, items]);

  const sentinelRef = useInfiniteScroll({
    hasNextPage: activeQuery.hasNextPage,
    isFetchingNextPage: activeQuery.isFetchingNextPage,
    fetchNextPage: activeQuery.fetchNextPage,
  });

  // is_personalized only exists on feed response, not search response
  const isPersonalized = q.trim().length === 0 ? (feedQuery.data?.pages[0]?.is_personalized ?? false) : false;
  const total = activeQuery.data?.pages[0]?.total ?? 0;

  if (isRedirecting) return null;

  return (
    <AppShell activeTab="for-you">
      <div className="flex gap-6">
        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h1
                  className="text-xl font-semibold tracking-tight"
                  style={{ color: "rgba(230, 233, 242, 0.95)" }}
                >
                  {q.trim().length > 0 ? "Search Results" : "For You"}
                </h1>
                <p className="mt-1 text-sm" style={{ color: "rgba(138, 144, 178, 1)" }}>
                  {q.trim().length > 0
                    ? `${total} results for "${q}"`
                    : isPersonalized
                    ? "Issues tailored to your skills and interests"
                    : "Complete your profile for personalized recommendations"}
                </p>
              </div>
              <div className="text-[12px] font-medium" style={{ color: "#64748B" }}>
                {meQuery.data ? `Signed in as ${meQuery.data.email}` : "Guest"}
              </div>
            </div>
          </div>

          {/* Show ProfileCTA if not personalized and not searching */}
          {q.trim().length === 0 && !isPersonalized && !feedQuery.isLoading && !feedQuery.isError && (
            <ProfileCTA />
          )}

          {activeQuery.isLoading ? (
            <SkeletonList rows={10} />
          ) : activeQuery.isError ? (
            <EmptyState
              title="Sign in required"
              description={getApiErrorMessage(activeQuery.error) + " — go to Login to continue."}
            />
          ) : items.length === 0 ? (
            <EmptyState title={q.trim().length > 0 ? "No issues match your query" : "No recommendations match your filters"} />
          ) : (
            <>
              <div
                className="rounded-2xl overflow-hidden"
                style={{
                  backgroundColor: "rgba(17, 20, 32, 0.5)",
                  border: "1px solid rgba(255, 255, 255, 0.04)",
                }}
              >
                {items.map((issue) => (
                  <div
                    key={issue.nodeId}
                    onClick={() => {
                      setSelectedIssueId(issue.nodeId);
                      if (q.trim().length > 0) {
                        const searchCtx = searchContextByNodeId.get(issue.nodeId);
                        if (searchCtx) {
                          logSearchInteraction.mutate({
                            search_id: searchCtx.searchId,
                            selected_node_id: issue.nodeId,
                            position: searchCtx.position,
                          });
                        }
                        return;
                      }

                      const recommendationCtx = recommendationContextByNodeId.get(issue.nodeId);
                      if (!recommendationCtx) return;

                      logRecommendationEvents.mutate({
                        recommendation_batch_id: recommendationCtx.recommendationBatchId,
                        events: [
                          {
                            event_id: crypto.randomUUID(),
                            event_type: "click",
                            issue_node_id: issue.nodeId,
                            position: recommendationCtx.position,
                            surface: "for-you",
                          },
                        ],
                      });
                    }}
                    className="btn-press cursor-pointer transition-colors hover:bg-white/[0.02]"
                    style={{
                      backgroundColor:
                        selectedIssueId === issue.nodeId ? "rgba(138, 92, 255, 0.08)" : undefined,
                      boxShadow:
                        selectedIssueId === issue.nodeId
                          ? "inset 2px 0 0 rgba(138, 92, 255, 0.6)"
                          : "none",
                    }}
                  >
                    <IssueListItem
                      issue={issue}
                      href={`/issues/${issue.nodeId}` as Route}
                      isSaved={!!bookmarksMap[issue.nodeId]}
                      onToggleSaved={() => handleToggleBookmark(issue)}
                    />
                  </div>
                ))}
              </div>

              {/* Infinite scroll */}
              {activeQuery.hasNextPage && (
                <div ref={sentinelRef} className="py-8 flex justify-center">
                  <div className="animate-spin h-6 w-6 border-2 border-purple-500 border-t-transparent rounded-full" />
                </div>
              )}
            </>
          )}
        </div>

        {/* Detail panel */}
        {selectedIssue && (
          <IssueDetailPanel
            issue={selectedIssue}
            onClose={() => setSelectedIssueId(null)}
            isBookmarked={!!bookmarksMap[selectedIssue.nodeId]}
            onToggleBookmark={() => {
              const found = items.find((i) => i.nodeId === selectedIssue.nodeId);
              if (found) handleToggleBookmark(found);
            }}
            onViewSimilar={() => router.push(`/issues/${selectedIssue.nodeId}`)}
          />
        )}
      </div>
    </AppShell>
  );
}
