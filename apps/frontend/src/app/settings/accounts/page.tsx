import { redirect } from "next/navigation";
import type { Route } from "next";

export default function SettingsAccountsRedirectPage({
  searchParams,
}: {
  searchParams?: { error?: string };
}) {
  const error = searchParams?.error;
  const target = error
    ? `/profile?tab=accounts&error=${encodeURIComponent(error)}`
    : "/profile?tab=accounts";
  redirect(target as Route);
}
