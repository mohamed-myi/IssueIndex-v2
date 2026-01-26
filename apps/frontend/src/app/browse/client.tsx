"use client";

import type { Route } from "next";
import { useMemo, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/common/EmptyState";
import { SkeletonList } from "@/components/common/SkeletonList";
import { LoadMoreButton } from "@/components/common/LoadMoreButton";
import { IssueListItem, type IssueListItemModel } from "@/components/issues/IssueListItem";
import { IssueDetailPanel, type IssueDetailModel } from "@/components/issues/IssueDetailPanel";
import { useSearch, useTrending, useBookmarkCheck, useCreateBookmark, useDeleteBookmark, useMe } from "@/lib/api/hooks";

export default function BrowseClient() {
  const sp = useSearchParams();
  const router = useRouter();

  const q = sp.get("q") ?? "";
  const lang = sp.get("lang") ?? null;
  const label = sp.get("label") ?? null;
  const repo = sp.get("repo") ?? null;

  const [page, setPage] = useState(1);
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);

  const meQuery = useMe();

  const searchQuery = useSearch({
    query: q,
    filters: {
      languages: lang ? [lang] : undefined,
      labels: label ? [label] : undefined,
      repos: repo ? [repo] : undefined,
    },
    page,
    pageSize: 20,
    enabled: q.trim().length > 0,
  });

  const trendingQuery = useTrending(20);

  const items = useMemo(() => {
    if (q.trim().length > 0) {
      const results = searchQuery.data?.results ?? [];
      return results.map<IssueListItemModel>((r) => ({
        nodeId: r.node_id,
        title: r.title,
        repoName: r.repo_name,
        primaryLanguage: r.primary_language,
        labels: r.labels,
        qScore: r.q_score,
        createdAt: r.github_created_at,
        bodyPreview: r.body_preview,
      }));
    }

    const results = trendingQuery.data?.results ?? [];
    return results
      .filter((r) => (lang ? r.primary_language === lang : true))
      .filter((r) => (repo ? r.repo_name === repo : true))
      .filter((r) => (label ? r.labels.includes(label) : true))
      .map<IssueListItemModel>((r) => ({
        nodeId: r.node_id,
        title: r.title,
        repoName: r.repo_name,
        primaryLanguage: r.primary_language,
        labels: r.labels,
        qScore: r.q_score,
        createdAt: r.github_created_at,
        bodyPreview: r.body_preview,
      }));
  }, [q, searchQuery.data, trendingQuery.data, lang, label, repo]);

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
          github_url: `https://github.com/${issue.repoName}`,
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
    } as IssueDetailModel;
  }, [selectedIssueId, items]);

  const isLoading = q.trim().length > 0 ? searchQuery.isLoading : trendingQuery.isLoading;
  const hasMore = q.trim().length > 0 ? (searchQuery.data?.has_more ?? false) : false;
  const total = q.trim().length > 0 ? (searchQuery.data?.total ?? 0) : items.length;
  const remaining = Math.max(0, total - items.length);

  function handleLoadMore() {
    setPage((p) => p + 1);
  }

  return (
    <AppShell activeTab="browse">
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
                  Browse
                </h1>
                <p className="mt-1 text-sm" style={{ color: "rgba(138, 144, 178, 1)" }}>
                  {q.trim().length > 0
                    ? `${searchQuery.data?.total ?? 0} results for "${q}"`
                    : "Search issues or explore trending ones"}
                </p>
              </div>
              <div className="text-[12px] font-medium" style={{ color: "#64748B" }}>
                {meQuery.data ? `Signed in as ${meQuery.data.email}` : "Guest"}
              </div>
            </div>
          </div>

          {isLoading ? (
            <SkeletonList rows={10} />
          ) : items.length === 0 ? (
            <EmptyState title="No issues match your query" />
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
                    onClick={() => setSelectedIssueId(issue.nodeId)}
                    className="cursor-pointer"
                    style={{
                      backgroundColor:
                        selectedIssueId === issue.nodeId ? "rgba(138, 92, 255, 0.08)" : "transparent",
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

              {hasMore && (
                <LoadMoreButton
                  onClick={handleLoadMore}
                  isLoading={searchQuery.isFetching && page > 1}
                  remaining={remaining}
                />
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
