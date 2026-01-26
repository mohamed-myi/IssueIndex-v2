import ProfileClient from "./profile-client";
import { Suspense } from "react";

export const dynamic = "force-dynamic";

export default function ProfilePage({
  searchParams,
}: {
  searchParams?: { tab?: string; connected?: string };
}) {
  const tab = searchParams?.tab ?? "overview";
  const connected = searchParams?.connected ?? null;

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
      <ProfileClient initialTab={tab} connected={connected} />
    </Suspense>
  );
}

