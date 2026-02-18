import { redirect } from "next/navigation";
import type { Route } from "next";

export default async function SettingsAccountsRedirectPage({
  searchParams,
}: {
  searchParams?: Promise<{ error?: string }>;
}) {
  const resolvedParams = searchParams ? await searchParams : undefined;
  const error = resolvedParams?.error;
  const target = error
    ? `/profile?tab=accounts&error=${encodeURIComponent(error)}`
    : "/profile?tab=accounts";
  redirect(target as Route);
}
