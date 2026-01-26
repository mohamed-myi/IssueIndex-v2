import { redirect } from "next/navigation";
import type { Route } from "next";

export default function ProfileOnboardingRedirectPage() {
  redirect("/profile?tab=onboarding" as Route);
}

