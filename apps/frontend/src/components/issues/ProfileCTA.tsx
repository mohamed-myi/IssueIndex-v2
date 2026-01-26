"use client";

import Link from "next/link";
import type { Route } from "next";
import { Sparkles, ArrowRight } from "lucide-react";

type ProfileCTAProps = {
  title?: string;
  description?: string;
  ctaText?: string;
  ctaHref?: Route;
};

export function ProfileCTA({
  title = "Complete your profile for better recommendations",
  description = "Tell us about your skills and interests to get personalized issue suggestions that match your expertise.",
  ctaText = "Complete profile",
  ctaHref = "/profile?tab=onboarding" as Route,
}: ProfileCTAProps) {
  return (
    <div
      className="rounded-2xl p-6 mb-6"
      style={{
        background: `linear-gradient(
          135deg,
          rgba(99, 102, 241, 0.08),
          rgba(138, 92, 255, 0.04)
        )`,
        border: "1px solid rgba(99, 102, 241, 0.15)",
      }}
    >
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div
          className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(138, 92, 255, 0.15))",
            border: "1px solid rgba(99, 102, 241, 0.25)",
          }}
        >
          <Sparkles
            className="w-5 h-5"
            style={{ color: "rgba(138, 92, 255, 0.95)" }}
          />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3
            className="text-[15px] font-semibold mb-1"
            style={{ color: "rgba(230, 233, 242, 0.95)" }}
          >
            {title}
          </h3>
          <p
            className="text-[13px] leading-relaxed mb-4"
            style={{ color: "rgba(138, 144, 178, 1)" }}
          >
            {description}
          </p>

          <Link
            href={ctaHref}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-[13px] font-semibold transition-all duration-200 hover:translate-y-[-1px]"
            style={{
              backgroundColor: "rgba(99, 102, 241, 0.15)",
              border: "1px solid rgba(99, 102, 241, 0.35)",
              color: "rgba(255, 255, 255, 0.95)",
            }}
          >
            {ctaText}
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
