"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";
import { authConnectGithubCallback } from "@/lib/api/endpoints";
import { getApiErrorMessage } from "@/lib/api/client";
import { getFingerprint } from "@/lib/fingerprint";

export default function GithubConnectCallbackClient() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const code = searchParams.get("code") ?? undefined;
  const state = searchParams.get("state") ?? undefined;
  const error = searchParams.get("error") ?? undefined;

  const [message, setMessage] = useState("Connecting GitHub...");

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        const fingerprint = await getFingerprint();
        await authConnectGithubCallback({ code, state, error, fingerprint });
        if (!cancelled) {
          router.replace("/profile?tab=onboarding&connected=github" as Route);
        }
      } catch (e) {
        if (!cancelled) {
          setMessage(getApiErrorMessage(e));
        }
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [code, state, error, router]);

  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Connecting GitHub</h1>
      <p className="mt-3 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
        {message}
      </p>
    </main>
  );
}

