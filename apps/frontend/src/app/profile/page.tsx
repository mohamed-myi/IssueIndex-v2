import ProfileClient from "./profile-client";
import { Suspense } from "react";

export const dynamic = "force-dynamic";

export default async function ProfilePage({
  searchParams,
}: {
  searchParams?: Promise<{ tab?: string; connected?: string; error?: string }>;
}) {
  const resolvedParams = searchParams ? await searchParams : undefined;
  const tab = resolvedParams?.tab ?? "overview";
  const connected = resolvedParams?.connected ?? null;
  const error = resolvedParams?.error ?? null;

  return (
    <Suspense
      fallback={
        <main className="mx-auto max-w-5xl px-6 py-16">
          <div className="text-sm" style={{ color: "rgba(138,144,178,1)" }}>
            Loading…
          </div>
        </main>
      }
    >
      <ProfileClient initialTab={tab} connected={connected} initialError={error} />
    </Suspense>
  );
}
