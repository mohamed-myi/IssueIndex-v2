import { Suspense } from "react";
import DashboardClient from "./client";

export const dynamic = "force-dynamic";

export default function DashboardPage() {
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
      <DashboardClient />
    </Suspense>
  );
}

