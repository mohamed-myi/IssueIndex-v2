import { redirect } from "next/navigation";
import type { Route } from "next";

export default function ProfileOnboardingRedirectPage({
  searchParams,
}: {
  searchParams?: { connected?: string; error?: string };
}) {
  const params = new URLSearchParams();
  params.set("tab", "onboarding");
  if (searchParams?.connected) params.set("connected", searchParams.connected);
  if (searchParams?.error) params.set("error", searchParams.error);
  redirect(`/profile?${params.toString()}` as Route);
}
