import { redirect } from "next/navigation";
import type { Route } from "next";

export default function SettingsAccountsRedirectPage() {
  redirect("/profile?tab=accounts" as Route);
}

