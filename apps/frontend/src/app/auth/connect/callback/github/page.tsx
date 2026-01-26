import { Suspense } from "react";
import GithubConnectCallbackClient from "./client";

export const dynamic = "force-dynamic";

export default function GithubConnectCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto max-w-md px-6 py-16">
          <h1 className="text-2xl font-semibold tracking-tight">Connecting GitHub</h1>
          <p className="mt-3 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
            Loading…
          </p>
        </main>
      }
    >
      <GithubConnectCallbackClient />
    </Suspense>
  );
}

