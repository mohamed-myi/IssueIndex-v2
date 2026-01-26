"use client";

import { useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { MessageSquare, Activity, ChevronDown, ChevronUp } from "lucide-react";

export type IssueCardModel = {
  nodeId: string;
  title: string;
  repoName: string;
  primaryLanguage: string | null;
  labels: string[];
  qScore: number | null;
  bodyPreview: string | null;
  commentsCount?: number;
  matchReason?: string;
  matchScore?: number;
};

type IssueCardProps = {
  issue: IssueCardModel;
  href: Route;
  showMatchReason?: boolean;
};

const languageColors: Record<string, string> = {
  Python: "#3776ab",
  TypeScript: "#3178c6",
  JavaScript: "#f7df1e",
  Go: "#00add8",
  Rust: "#ce422b",
  Java: "#007396",
  Ruby: "#cc342d",
  PHP: "#777bb4",
  "C++": "#00599c",
  "C#": "#239120",
  Swift: "#f05138",
  Kotlin: "#7f52ff",
};

export function IssueCard({ issue, href, showMatchReason = false }: IssueCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const score = issue.qScore;
  const displayScore = score !== null ? Math.round(score * 100) : null;
  const langColor = issue.primaryLanguage ? languageColors[issue.primaryLanguage] ?? "#6366f1" : "#666";

  return (
    <Link
      href={href}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="group block transition-all duration-500 relative"
    >
      {/* Spotlight glow effect */}
      {isHovered && (
        <div
          className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none -z-10"
          style={{
            background:
              "radial-gradient(600px circle at 50% 50%, rgba(99, 102, 241, 0.1), transparent 40%)",
          }}
        />
      )}

      <div
        className="rounded-2xl overflow-hidden transition-all duration-500 relative"
        style={{
          backgroundColor: isHovered ? "rgba(24, 24, 27, 1)" : "rgba(24, 24, 27, 0.95)",
          boxShadow: isHovered
            ? "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(99, 102, 241, 0.2)"
            : "0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -4px rgba(0, 0, 0, 0.5)",
        }}
      >
        <div className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between gap-4 mb-3">
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-semibold text-white mb-2 leading-snug tracking-tight line-clamp-2">
                {issue.title}
              </h3>
              <div className="flex items-center gap-2.5 text-xs" style={{ color: "#71717a" }}>
                <span>{issue.repoName}</span>
                <span style={{ color: "#3f3f46" }}>·</span>
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: langColor }}
                  />
                  <span>{issue.primaryLanguage ?? "Unknown"}</span>
                </div>
              </div>
            </div>

            {/* Quality Score */}
            {displayScore !== null && (
              <div
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-300"
                style={{
                  backgroundColor: "rgba(34, 197, 94, 0.1)",
                }}
              >
                <Activity className="w-4 h-4 text-green-500" />
                <span className="text-xs text-green-400 font-medium tabular-nums">
                  {displayScore}
                </span>
              </div>
            )}
          </div>

          {/* Snippet */}
          {issue.bodyPreview && (
            <p
              className="text-sm mb-5 leading-relaxed line-clamp-2"
              style={{ color: "#a1a1aa" }}
            >
              {issue.bodyPreview}
            </p>
          )}

          {/* Labels & Comments */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              {issue.labels.slice(0, 3).map((label) => (
                <span
                  key={label}
                  className="px-2.5 py-1 rounded-md text-xs transition-all duration-200"
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.05)",
                    color: "#a1a1aa",
                  }}
                >
                  {label}
                </span>
              ))}
              {issue.labels.length > 3 && (
                <span
                  className="px-2 py-1 text-xs"
                  style={{ color: "#71717a" }}
                >
                  +{issue.labels.length - 3}
                </span>
              )}
            </div>

            {typeof issue.commentsCount === "number" && (
              <div className="flex items-center gap-1.5" style={{ color: "#71717a" }}>
                <MessageSquare className="w-4 h-4" />
                <span className="text-xs tabular-nums">{issue.commentsCount}</span>
              </div>
            )}
          </div>

          {/* Match Reason (For You section) */}
          {showMatchReason && issue.matchReason && (
            <div
              className="mt-5 pt-5"
              style={{ borderTop: "1px solid rgba(255, 255, 255, 0.05)" }}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsExpanded(!isExpanded);
                }}
                className="flex items-center gap-2 text-xs transition-colors w-full"
                style={{ color: "#71717a" }}
              >
                <span>Why this?</span>
                {isExpanded ? (
                  <ChevronUp className="w-3.5 h-3.5" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5" />
                )}
              </button>

              {isExpanded && (
                <div className="mt-3 space-y-3 animate-in fade-in duration-200">
                  <p className="text-xs leading-relaxed" style={{ color: "#a1a1aa" }}>
                    {issue.matchReason}
                  </p>
                  {typeof issue.matchScore === "number" && (
                    <div className="flex items-center gap-3">
                      <span
                        className="text-[10px] tracking-wide"
                        style={{ color: "#52525b" }}
                      >
                        Match
                      </span>
                      <div
                        className="flex-1 h-1.5 rounded-full overflow-hidden"
                        style={{ backgroundColor: "rgba(255, 255, 255, 0.05)" }}
                      >
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${issue.matchScore}%`,
                            background: "linear-gradient(to right, #6366f1, #06b6d4)",
                          }}
                        />
                      </div>
                      <span className="text-xs font-medium tabular-nums" style={{ color: "#a1a1aa" }}>
                        {issue.matchScore}%
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
