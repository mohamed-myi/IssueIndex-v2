"use client";

import Link from "next/link";
import { TopNav } from "@/components/layout/TopNav";

const TABLE_OF_CONTENTS = [
  { id: "what-is-issueindex", label: "What is IssueIndex?", level: 1 },
  { id: "core-features", label: "Core Features", level: 1 },
  { id: "search-browse", label: "Search & Browse", level: 2 },
  { id: "trending-issues", label: "Trending Issues", level: 2 },
  { id: "personalized-feed", label: "Personalized Feed", level: 2 },
  { id: "bookmarks-notes", label: "Bookmarks & Notes", level: 2 },
  { id: "similar-issues", label: "Similar Issues", level: 2 },
  { id: "how-it-works", label: "How It Works", level: 1 },
  { id: "issue-indexing", label: "Issue Indexing", level: 2 },
  { id: "quality-scoring", label: "Quality Scoring", level: 2 },
  { id: "personalization", label: "Personalization", level: 2 },
  { id: "profile-sources", label: "Profile Sources", level: 2 },
  { id: "getting-started", label: "Getting Started", level: 1 },
  { id: "sessions-limits", label: "Sessions & Limits", level: 1 },
  { id: "account-management", label: "Account Management", level: 1 },
];

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <TopNav activeTab={null} sidebarOpen={false} onToggleSidebar={() => { }} />

      {/* Main layout */}
      <main className="pt-[var(--topnav-height)]">
        <div className="max-w-6xl mx-auto px-6 py-12 lg:grid lg:grid-cols-[1fr_200px] lg:gap-12">
          {/* Main content */}
          <article>
            {/* Page header */}
            <header className="mb-12">
              <h1
                className="text-3xl font-bold tracking-tight mb-4"
                style={{ color: "rgba(230, 233, 242, 0.98)" }}
              >
                Documentation
              </h1>
              <p
                className="text-lg leading-relaxed"
                style={{ color: "rgba(138, 144, 178, 1)" }}
              >
                Learn how IssueIndex works and how to get the most out of it.
              </p>
            </header>

            {/* What is IssueIndex? */}
            <section className="mb-12">
              <h2
                id="what-is-issueindex"
                className="text-xl font-semibold tracking-tight mb-4 scroll-mt-20"
                style={{ color: "rgba(230, 233, 242, 0.95)" }}
              >
                What is IssueIndex?
              </h2>
              <p className="mb-4 text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                IssueIndex aggregates open issues from popular GitHub repositories, scores them for quality, and presents them in a searchable format. The goal is to reduce the time spent hunting for contribution opportunities by surfacing issues that are well-documented and actively maintained.
              </p>
              <ul className="space-y-2 text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>Semantic and keyword search with filters for language, labels and repositories</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>Optional profile-based recommendations using your GitHub activity, resume, or stated interests</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>Bookmarks and notes for tracking issues you are interested in</span>
                </li>
              </ul>
            </section>

            {/* Core Features */}
            <section className="mb-12">
              <h2
                id="core-features"
                className="text-xl font-semibold tracking-tight mb-6 scroll-mt-20"
                style={{ color: "rgba(230, 233, 242, 0.95)" }}
              >
                Core Features
              </h2>

              <div className="space-y-8">
                <div>
                  <h3
                    id="search-browse"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    Search/Browse
                  </h3>
                  <p className="text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    Search combines semantic understanding with keyword matching. You can describe what you are looking for in natural language, and results can be filtered by programming language, labels (such as &quot;good first issue&quot;), or specific repositories.
                  </p>
                </div>

                <div>
                  <h3
                    id="trending-issues"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    Trending Issues
                  </h3>
                  <p className="text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    The trending view ranks issues by a combination of quality score and recency. This is the default view for users who have not set up a profile.
                  </p>
                </div>

                <div>
                  <h3
                    id="personalized-feed"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    For You Page
                  </h3>
                  <p className="text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    After completing onboarding, the For You page shows issues matched to your profile. Your profile can be built from three optional sources: manually entered interests, an uploaded resume or your public GitHub activity. Each source contributes to the matching, with manual interests weighted most heavily.
                  </p>
                </div>

                <div>
                  <h3
                    id="bookmarks-notes"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    Bookmarks & Notes
                  </h3>
                  <p className="text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    Bookmark issues to save them for later. Each bookmark supports personal notes and a resolved status for tracking your progress.
                  </p>
                </div>

                <div>
                  <h3
                    id="similar-issues"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    Similar Issues
                  </h3>
                  <p className="text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    Each issue detail page displays semantically similar issues, useful for finding alternatives or exploring related work.
                  </p>
                </div>
              </div>
            </section>

            {/* How It Works */}
            <section className="mb-12">
              <h2
                id="how-it-works"
                className="text-xl font-semibold tracking-tight mb-6 scroll-mt-20"
                style={{ color: "rgba(230, 233, 242, 0.95)" }}
              >
                How It Works
              </h2>

              <div className="space-y-8">
                <div>
                  <h3
                    id="issue-indexing"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    Issue Indexing
                  </h3>
                  <p className="text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    A background process fetches issues from high-activity repositories across multiple programming languages. Issues are filtered for structural quality before being added to the index. Closed or stale issues are periodically removed.
                  </p>
                </div>

                <div>
                  <h3
                    id="quality-scoring"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    Quality Scoring (Q-Score)
                  </h3>
                  <p className="text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    Each issue is assigned a quality score (Q-Score) based on structural factors: whether the description includes code blocks, follows a template with sections like &quot;Steps to Reproduce&quot; and contains relevant technical keywords. Low-quality issues are filtered out during indexing. You can set a minimum Q-Score threshold in your preferences to further filter results.
                  </p>
                </div>

                <div>
                  <h3
                    id="personalization"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    Personalization
                  </h3>
                  <p className="text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    Your profile is represented as a vector that captures your skills and interests. Issues are also represented as vectors based on their content. The For You page ranks issues by how closely they match your profile vector. You can update your profile at any time by editing your interests, uploading a new resume or refreshing your GitHub connection.
                  </p>
                </div>

                <div>
                  <h3
                    id="profile-sources"
                    className="text-base font-medium mb-2 scroll-mt-20"
                    style={{ color: "rgba(230, 233, 242, 0.90)" }}
                  >
                    Profile Sources
                  </h3>
                  <p className="mb-3 text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    Each profile source contributes to your combined profile with the following weights:
                  </p>
                  <ul className="space-y-2 text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    <li className="flex items-start gap-2">
                      <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                      <span><strong style={{ color: "rgba(230, 233, 242, 0.90)" }}>Intent (50%)</strong> - Languages, stack areas and free-text description entered during onboarding</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                      <span><strong style={{ color: "rgba(230, 233, 242, 0.90)" }}>Resume (30%)</strong> - Skills and job titles extracted from an uploaded PDF or DOCX (max 5MB)</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                      <span><strong style={{ color: "rgba(230, 233, 242, 0.90)" }}>GitHub (20%)</strong> - Languages and topics from your starred and contributed repositories</span>
                    </li>
                  </ul>
                  <p className="mt-3 text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                    If fewer than three sources are provided, the weights redistribute proportionally among the sources you have.
                  </p>
                </div>
              </div>
            </section>

            {/* Getting Started */}
            <section className="mb-12">
              <h2
                id="getting-started"
                className="text-xl font-semibold tracking-tight mb-6 scroll-mt-20"
                style={{ color: "rgba(230, 233, 242, 0.95)" }}
              >
                Getting Started
              </h2>

              <ol className="space-y-6 text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                <li>
                  <span className="font-medium" style={{ color: "rgba(230, 233, 242, 0.90)" }}>
                    1. Browse or search
                  </span>
                  <p className="mt-1">
                    No account is required. Use the search bar or browse trending issues to explore the index.
                  </p>
                </li>
                <li>
                  <span className="font-medium" style={{ color: "rgba(230, 233, 242, 0.90)" }}>
                    2. Sign in (optional)
                  </span>
                  <p className="mt-1">
                    Sign in with GitHub or Google to unlock bookmarks and the For You page. Signing in with GitHub does not automatically grant access to your repositories; profile data requires a separate connection step.
                  </p>
                </li>
                <li>
                  <span className="font-medium" style={{ color: "rgba(230, 233, 242, 0.90)" }}>
                    3. Complete onboarding
                  </span>
                  <p className="mt-1">
                    During onboarding, you can enter your interests manually, upload a resume or connect your GitHub account for activity analysis. All three are optional; providing any one enables the For You page.
                  </p>
                </li>
                <li>
                  <span className="font-medium" style={{ color: "rgba(230, 233, 242, 0.90)" }}>
                    4. Adjust preferences
                  </span>
                  <p className="mt-1">
                    In settings, you can filter results by preferred languages and set a minimum Q-Score threshold.
                  </p>
                </li>
              </ol>
            </section>

            {/* Sessions & Limits */}
            <section className="mb-12">
              <h2
                id="sessions-limits"
                className="text-xl font-semibold tracking-tight mb-6 scroll-mt-20"
                style={{ color: "rgba(230, 233, 242, 0.95)" }}
              >
                Sessions & Limits
              </h2>
              <ul className="space-y-2 text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>Sessions expire after 24 hours of inactivity, or 7 days if you select &quot;Remember me&quot; during login</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>Anonymous users are limited to 10 searches per minute; authenticated users have 60 per minute</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>GitHub profile data can be refreshed once per hour</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>The default minimum Q-Score threshold (matching algorithm) is 0.6, adjustable in preferences</span>
                </li>
              </ul>
            </section>

            {/* Account Management */}
            <section className="mb-12">
              <h2
                id="account-management"
                className="text-xl font-semibold tracking-tight mb-6 scroll-mt-20"
                style={{ color: "rgba(230, 233, 242, 0.95)" }}
              >
                Account Management
              </h2>
              <ul className="space-y-2 text-[15px] leading-relaxed" style={{ color: "rgba(138, 144, 178, 1)" }}>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>You can link multiple OAuth providers (GitHub and Google) to the same account</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>Active sessions are listed in settings; you can revoke individual sessions or all sessions at once</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-2 w-1 h-1 rounded-full flex-shrink-0 bg-white/40" />
                  <span>Deleting your account removes all stored data including bookmarks, notes and profile information</span>
                </li>
              </ul>
            </section>

            {/* Footer */}
            <footer
              className="pt-8 text-sm"
              style={{
                borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                color: "rgba(138, 144, 178, 0.6)",
              }}
            >
              <p>
                Status: In Development{" "}
                <Link href="/" className="underline hover:text-white transition-colors">
                  Return to Home Screen
                </Link>
              </p>
            </footer>
          </article>

          {/* Right sidebar - Table of Contents */}
          <aside className="hidden lg:block">
            <nav className="sticky top-24">
              <h4
                className="text-[11px] font-semibold uppercase tracking-widest mb-4"
                style={{ color: "rgba(138, 144, 178, 0.6)" }}
              >
                On This Page
              </h4>
              <ul className="space-y-2">
                {TABLE_OF_CONTENTS.map((item) => (
                  <li key={item.id}>
                    <a
                      href={`#${item.id}`}
                      className={`block text-[13px] transition-colors hover:text-white ${item.level === 2 ? "pl-3" : ""
                        }`}
                      style={{ color: "rgba(138, 144, 178, 0.8)" }}
                    >
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </aside>
        </div>
      </main>
    </div>
  );
}
