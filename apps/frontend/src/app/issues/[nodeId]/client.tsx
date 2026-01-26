"use client";

import Link from "next/link";
import { useMemo, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { ExternalLink, Bookmark, MessageCircle } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/common/EmptyState";
import { SkeletonList } from "@/components/common/SkeletonList";
import { getApiErrorMessage } from "@/lib/api/client";
import type { Route } from "next";
import {
  useIssue,
  useSimilarIssues,
  useMe,
  useBookmarkCheck,
  useCreateBookmark,
} from "@/lib/api/hooks";

export default function IssueDetailPage() {
  const params = useParams<{ nodeId: string }>();
  const nodeId = params.nodeId;

  const [toast, setToast] = useState<string | null>(null);

  const meQuery = useMe();
  const issueQuery = useIssue(nodeId);
  const similarQuery = useSimilarIssues(nodeId, 5);
  const bookmarkCheckQuery = useBookmarkCheck([nodeId]);
  const createBookmark = useCreateBookmark();

  const isSaved = useMemo(
    () => Boolean(bookmarkCheckQuery.data?.bookmarks?.[nodeId]),
    [bookmarkCheckQuery.data, nodeId],
  );

  const handleSave = useCallback(() => {
    const issue = issueQuery.data;
    if (!issue) return;

    createBookmark.mutate(
      {
        issue_node_id: issue.node_id,
        github_url: issue.github_url,
        title_snapshot: issue.title,
        body_snapshot: issue.body.slice(0, 5000),
      },
      {
        onSuccess: () => setToast("Issue saved to bookmarks"),
        onError: (e) => setToast(getApiErrorMessage(e)),
      },
    );
  }, [issueQuery.data, createBookmark]);

  if (issueQuery.isLoading) {
    return (
      <AppShell activeTab={null}>
        <SkeletonList rows={6} />
      </AppShell>
    );
  }

  if (issueQuery.isError) {
    return (
      <AppShell activeTab={null}>
        <EmptyState title="Unable to load issue" description={getApiErrorMessage(issueQuery.error)} />
        <div className="mt-4 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
          <Link className="underline underline-offset-2" href="/login">
            Log in
          </Link>{" "}
          if this is an authenticated-only page.
        </div>
      </AppShell>
    );
  }

  const issue = issueQuery.data;
  if (!issue) {
    return (
      <AppShell activeTab={null}>
        <EmptyState title="Unable to load issue" description="Issue data is missing." />
      </AppShell>
    );
  }

  const scoreColor =
    issue.q_score >= 0.9
      ? "rgba(34, 197, 94, 0.95)"
      : issue.q_score >= 0.8
        ? "rgba(99, 102, 241, 0.95)"
        : "rgba(234, 179, 8, 0.95)";

  return (
    <AppShell activeTab={null}>
      <div className="flex gap-8">
        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="mb-6">
            <div
              className="text-xs font-semibold uppercase tracking-widest mb-2"
              style={{ color: "#71717a" }}
            >
              {issue.repo_name}
            </div>
            <h1
              className="text-2xl font-semibold tracking-tight leading-tight"
              style={{ color: "rgba(230, 233, 242, 0.95)" }}
            >
              {issue.title}
            </h1>
            <div
              className="mt-3 flex flex-wrap items-center gap-3 text-sm"
              style={{ color: "rgba(138,144,178,1)" }}
            >
              <span
                className="px-2 py-0.5 rounded-md text-xs font-semibold"
                style={{
                  backgroundColor:
                    issue.state === "open" ? "rgba(34, 197, 94, 0.12)" : "rgba(138, 92, 255, 0.12)",
                  color: issue.state === "open" ? "#86efac" : "#c4b5fd",
                }}
              >
                {issue.state}
              </span>
              <span>{issue.primary_language}</span>
              <span>·</span>
              <span style={{ color: scoreColor }}>
                Score: {Math.round(issue.q_score * 100)}
              </span>
            </div>
          </div>

          {/* Toast */}
          {toast && (
            <div
              className="mb-6 rounded-xl border px-4 py-3 text-sm"
              style={{
                borderColor: "rgba(255,255,255,0.08)",
                backgroundColor: "rgba(24, 24, 27, 0.35)",
              }}
            >
              {toast}
            </div>
          )}

          {/* Labels */}
          {issue.labels.length > 0 && (
            <div className="mb-6 flex flex-wrap gap-2">
              {issue.labels.map((label) => (
                <span
                  key={label}
                  className="px-2.5 py-1 rounded-md text-[11px] font-medium"
                  style={{
                    backgroundColor: "rgba(99, 102, 241, 0.12)",
                    color: "rgba(255, 255, 255, 0.75)",
                    border: "1px solid rgba(99, 102, 241, 0.25)",
                  }}
                >
                  {label}
                </span>
              ))}
            </div>
          )}

          {/* Body */}
          <div
            className="rounded-2xl border p-6"
            style={{
              borderColor: "rgba(255,255,255,0.08)",
              backgroundColor: "rgba(24, 24, 27, 0.35)",
            }}
          >
            <div
              className="whitespace-pre-wrap text-sm leading-relaxed"
              style={{ color: "rgba(230, 233, 242, 0.85)" }}
            >
              {issue.body}
            </div>
          </div>

          {/* Actions */}
          <div className="mt-6 flex items-center gap-3">
            <a
              href={issue.github_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-semibold transition-all duration-200 hover:translate-y-[-1px]"
              style={{
                backgroundColor: "rgba(99, 102, 241, 0.90)",
                color: "rgba(255, 255, 255, 0.98)",
                border: "1px solid rgba(99, 102, 241, 0.5)",
              }}
            >
              <ExternalLink className="w-4 h-4" />
              View on GitHub
            </a>

            <button
              type="button"
              disabled={!meQuery.data || isSaved || createBookmark.isPending}
              onClick={handleSave}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 disabled:opacity-50"
              style={{
                backgroundColor: isSaved ? "rgba(138, 92, 255, 0.15)" : "rgba(255, 255, 255, 0.05)",
                border: `1px solid ${isSaved ? "rgba(138, 92, 255, 0.3)" : "rgba(255, 255, 255, 0.08)"}`,
                color: isSaved ? "#c4b5fd" : "rgba(255, 255, 255, 0.75)",
              }}
            >
              <Bookmark
                className="w-4 h-4"
                style={{ fill: isSaved ? "currentColor" : "none" }}
              />
              {isSaved ? "Saved" : "Save Issue"}
            </button>

            {!meQuery.data && (
              <Link
                href="/login"
                className="px-4 py-2.5 rounded-xl text-[13px] font-medium transition-colors hover:bg-white/5"
                style={{
                  border: "1px solid rgba(255,255,255,0.08)",
                  color: "rgba(255, 255, 255, 0.75)",
                }}
              >
                Log in to save
              </Link>
            )}
          </div>
        </div>

        {/* Similar issues sidebar */}
        <div className="w-80 flex-shrink-0">
          <div
            className="sticky top-24 rounded-2xl p-5"
            style={{
              backgroundColor: "rgba(17, 20, 32, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
            }}
          >
            <h2
              className="text-sm font-semibold mb-4"
              style={{ color: "rgba(230, 233, 242, 0.95)" }}
            >
              Similar Issues
            </h2>

            {similarQuery.isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse">
                    <div
                      className="h-4 rounded mb-2"
                      style={{ backgroundColor: "rgba(255, 255, 255, 0.06)", width: "80%" }}
                    />
                    <div
                      className="h-3 rounded"
                      style={{ backgroundColor: "rgba(255, 255, 255, 0.04)", width: "50%" }}
                    />
                  </div>
                ))}
              </div>
            ) : similarQuery.isError ? (
              <p className="text-xs" style={{ color: "rgba(138,144,178,1)" }}>
                Unable to load similar issues
              </p>
            ) : (similarQuery.data?.issues ?? []).length === 0 ? (
              <p className="text-xs" style={{ color: "rgba(138,144,178,1)" }}>
                No similar issues found
              </p>
            ) : (
              <div className="space-y-3">
                {(similarQuery.data?.issues ?? []).map((s) => (
                  <Link
                    key={s.node_id}
                    href={`/issues/${s.node_id}` as Route}
                    className="block p-3 rounded-xl transition-all duration-200 hover:bg-white/5"
                    style={{ border: "1px solid rgba(255, 255, 255, 0.04)" }}
                  >
                    <div
                      className="text-[13px] font-medium line-clamp-2 mb-1"
                      style={{ color: "rgba(230, 233, 242, 0.90)" }}
                    >
                      {s.title}
                    </div>
                    <div className="flex items-center justify-between">
                      <span
                        className="text-[11px]"
                        style={{ color: "rgba(138,144,178,1)" }}
                      >
                        {s.repo_name}
                      </span>
                      <span
                        className="text-[11px] font-medium"
                        style={{ color: "#a8aeff" }}
                      >
                        {Math.round(s.similarity_score * 100)}% match
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
