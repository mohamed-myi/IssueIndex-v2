import { redirect } from "next/navigation";
import type { Route } from "next";

export default async function ProfileOnboardingRedirectPage({
  searchParams,
}: {
  searchParams?: Promise<{ connected?: string; error?: string }>;
}) {
  const resolvedParams = searchParams ? await searchParams : undefined;
  const params = new URLSearchParams();
  params.set("tab", "onboarding");
  if (resolvedParams?.connected) params.set("connected", resolvedParams.connected);
  if (resolvedParams?.error) params.set("error", resolvedParams.error);
  redirect(`/profile?${params.toString()}` as Route);
}
