"use client";

import Link from "next/link";
import { Search, TrendingUp, Sparkles, ArrowRight, FileText, Target } from "lucide-react";
import { usePublicStats } from "@/lib/api/hooks";

export default function LandingPage() {
  const statsQuery = usePublicStats();

  return (
    <main className="min-h-screen">
      {/* Hero section */}
      <div className="relative overflow-hidden">
        {/* Background gradient effect */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `
              radial-gradient(800px circle at 30% 20%, rgba(99, 102, 241, 0.12), transparent 50%),
              radial-gradient(600px circle at 70% 60%, rgba(138, 92, 255, 0.08), transparent 50%)
            `,
          }}
        />

        <div className="relative max-w-6xl mx-auto px-6 pt-24 pb-16">
          <div className="max-w-3xl">
            {/* Badge */}
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold mb-6"
              style={{
                backgroundColor: "rgba(99, 102, 241, 0.12)",
                border: "1px solid rgba(99, 102, 241, 0.25)",
                color: "#a8aeff",
              }}
            >
              <Sparkles className="w-3.5 h-3.5" />
              Brought to you by MYI
            </div>

            {/* Heading */}
            <h1
              className="text-5xl font-bold tracking-tight leading-tight mb-6"
              style={{ color: "rgba(230, 233, 242, 0.98)" }}
            >
              Find GitHub issues worth your time,{" "}
              <span style={{ color: "#a8aeff" }}>selected specifically for you.</span>
            </h1>

            {/* Description */}
            <p
              className="text-lg leading-relaxed mb-8 max-w-2xl"
              style={{ color: "rgba(138, 144, 178, 1)" }}
            >
              Browse trending issues, search with powerful filters, and get personalized
              recommendations based on your skills and interests. Start contributing to
              projects that matter.
            </p>

            {/* CTA buttons */}
            <div className="flex flex-wrap gap-4">
              <Link
                href="/browse"
                className="flex items-center gap-2 px-6 py-3 rounded-xl text-[15px] font-semibold transition-all duration-200 hover:translate-y-[-2px]"
                style={{
                  backgroundColor: "rgba(99, 102, 241, 0.90)",
                  color: "rgba(255, 255, 255, 0.98)",
                  border: "1px solid rgba(99, 102, 241, 0.5)",
                  boxShadow: "0 4px 12px rgba(99, 102, 241, 0.3)",
                }}
              >
                <Search className="w-4 h-4" />
                Browse Issues
              </Link>

              <Link
                href="/dashboard"
                className="flex items-center gap-2 px-6 py-3 rounded-xl text-[15px] font-medium transition-all duration-200 hover:bg-white/5"
                style={{
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  color: "rgba(255, 255, 255, 0.85)",
                }}
              >
                <TrendingUp className="w-4 h-4" />
                View Trending
              </Link>
            </div>
          </div>

          {/* Sign-in CTA Tile - Full width */}
          <div
            className="mt-12 rounded-2xl p-6"
            style={{
              background: "linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(138, 92, 255, 0.04))",
              border: "1px solid rgba(99, 102, 241, 0.15)",
            }}
          >
            {/* Header row */}
            <div className="flex items-start justify-between gap-6 mb-6">
              <div className="flex-1">
                <h3
                  className="text-lg font-semibold mb-2"
                  style={{ color: "rgba(230, 233, 242, 0.95)" }}
                >
                  Unlock personalized recommendations
                </h3>
                <p
                  className="text-sm leading-relaxed max-w-2xl"
                  style={{ color: "rgba(138, 144, 178, 1)" }}
                >
                  Sign in with Google or GitHub to receive advanced recommendations based on your skills, experience, and goals.
                </p>
              </div>
              <Link
                href="/login"
                className="flex-shrink-0 flex items-center gap-2 px-5 py-2.5 rounded-xl text-[14px] font-semibold transition-all duration-200 hover:translate-y-[-2px]"
                style={{
                  backgroundColor: "rgba(99, 102, 241, 0.90)",
                  color: "rgba(255, 255, 255, 0.98)",
                  border: "1px solid rgba(99, 102, 241, 0.5)",
                  boxShadow: "0 4px 12px rgba(99, 102, 241, 0.3)",
                }}
              >
                Sign In
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            {/* Profile setup sub-tiles */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <ProfileMethodTile
                icon={
                  <svg className="w-5 h-5" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                  </svg>
                }
                title="GitHub History"
                description="Import your GitHub activity to match issues with your coding patterns and expertise"
              />
              <ProfileMethodTile
                icon={<FileText className="w-5 h-5" />}
                title="Resume Experience"
                description="Add your work experience and skills for better issue recommendations"
              />
              <ProfileMethodTile
                icon={<Target className="w-5 h-5" />}
                title="Your Goals"
                description="Tell us what you want to learn or contribute to"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Two-column Stats and Features section */}
      <div className="max-w-6xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          {/* Platform Statistics column */}
          <div>
            <div
              className="text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "#71717a" }}
            >
              Platform Statistics
            </div>
            <div className="flex flex-col gap-4">
              <StatCard
                label="Issues Indexed"
                value={statsQuery.data?.total_issues}
                icon={<Search className="w-5 h-5" />}
              />
              <StatCard
                label="Repositories"
                value={statsQuery.data?.total_repos}
                icon={
                  <svg className="w-5 h-5" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
                  </svg>
                }
              />
              <StatCard
                label="Languages"
                value={statsQuery.data?.total_languages}
                icon={
                  <svg className="w-5 h-5" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M.293 6.707a1 1 0 0 1 0-1.414l3-3a1 1 0 0 1 1.414 1.414L2.414 6l2.293 2.293a1 1 0 0 1-1.414 1.414l-3-3Zm14.414-3-3-3a1 1 0 0 1 1.414-1.414l3 3a1 1 0 0 1 0 1.414l-3 3a1 1 0 0 1-1.414-1.414L13.586 6l-2.293-2.293ZM8.5 1.5a1 1 0 0 0-1.964.37l1.5 8a1 1 0 1 0 1.964-.37l-1.5-8Z" />
                  </svg>
                }
              />
            </div>
          </div>

          {/* Features column */}
          <div>
            <div
              className="text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "#71717a" }}
            >
              Features
            </div>
            <div className="flex flex-col gap-4">
              <FeatureTile
                title="Smart Search"
                description="Filter by language, labels, and repositories. Find exactly what you're looking for."
                icon={<Search className="w-5 h-5" />}
              />
              <FeatureTile
                title="Trending Issues"
                description="Discover high-quality issues gaining traction across popular open source projects."
                icon={<TrendingUp className="w-5 h-5" />}
              />
              <FeatureTile
                title="Personalized Feed"
                description="Get recommendations tailored to your skills, interests, and contribution history."
                icon={<Sparkles className="w-5 h-5" />}
              />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function StatCard(props: { label: string; value?: number; icon: React.ReactNode }) {
  return (
    <div
      className="rounded-2xl p-6 transition-all duration-300 hover:translate-y-[-2px]"
      style={{
        backgroundColor: "rgba(17, 20, 32, 0.6)",
        border: "1px solid rgba(255, 255, 255, 0.06)",
      }}
    >
      <div className="flex items-center gap-3 mb-3">
        <div
          className="p-2 rounded-lg"
          style={{
            backgroundColor: "rgba(99, 102, 241, 0.12)",
            color: "#a8aeff",
          }}
        >
          {props.icon}
        </div>
        <div
          className="text-[11px] font-semibold uppercase tracking-widest"
          style={{ color: "#71717a" }}
        >
          {props.label}
        </div>
      </div>
      <div
        className="text-3xl font-bold tracking-tight"
        style={{ color: "rgba(230, 233, 242, 0.95)" }}
      >
        {typeof props.value === "number" ? props.value.toLocaleString() : "—"}
      </div>
    </div>
  );
}

function ProfileMethodTile(props: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div
      className="rounded-xl p-4"
      style={{
        backgroundColor: "rgba(17, 20, 32, 0.4)",
        border: "1px solid rgba(255, 255, 255, 0.06)",
      }}
    >
      <div className="flex items-center gap-3 mb-2">
        <div
          className="p-2 rounded-lg"
          style={{
            backgroundColor: "rgba(99, 102, 241, 0.12)",
            color: "#a8aeff",
          }}
        >
          {props.icon}
        </div>
        <div
          className="text-sm font-semibold"
          style={{ color: "rgba(230, 233, 242, 0.95)" }}
        >
          {props.title}
        </div>
      </div>
      <p
        className="text-xs leading-relaxed"
        style={{ color: "rgba(138, 144, 178, 1)" }}
      >
        {props.description}
      </p>
    </div>
  );
}

function FeatureTile(props: { title: string; description: string; icon: React.ReactNode }) {
  return (
    <div
      className="rounded-2xl p-5 transition-all duration-300 hover:translate-y-[-2px]"
      style={{
        backgroundColor: "rgba(17, 20, 32, 0.6)",
        border: "1px solid rgba(255, 255, 255, 0.06)",
      }}
    >
      <div className="flex items-center gap-3 mb-3">
        <div
          className="p-2 rounded-lg"
          style={{
            backgroundColor: "rgba(99, 102, 241, 0.12)",
            color: "#a8aeff",
          }}
        >
          {props.icon}
        </div>
        <div
          className="text-sm font-semibold"
          style={{ color: "rgba(230, 233, 242, 0.95)" }}
        >
          {props.title}
        </div>
      </div>
      <p
        className="text-sm leading-relaxed"
        style={{ color: "rgba(138, 144, 178, 1)" }}
      >
        {props.description}
      </p>
    </div>
  );
}
