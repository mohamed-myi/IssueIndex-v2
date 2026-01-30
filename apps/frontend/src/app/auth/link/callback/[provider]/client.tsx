"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";
import type { OAuthProvider } from "@/lib/api/types";
import { authLinkCallback } from "@/lib/api/endpoints";
import { getApiErrorMessage } from "@/lib/api/client";
import { getFingerprint } from "@/lib/fingerprint";

function isOAuthProvider(value: string): value is OAuthProvider {
  return value === "github" || value === "google";
}

export default function OAuthLinkCallbackClient() {
  const router = useRouter();
  const params = useParams<{ provider: string }>();
  const searchParams = useSearchParams();

  const provider = useMemo(() => {
    const raw = params?.provider ?? "";
    return isOAuthProvider(raw) ? raw : null;
  }, [params]);

  const code = searchParams.get("code") ?? undefined;
  const state = searchParams.get("state") ?? undefined;
  const error = searchParams.get("error") ?? undefined;

  const [message, setMessage] = useState("Linking account...");

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!provider) {
        setMessage("Invalid OAuth provider.");
        return;
      }

      try {
        const fingerprint = await getFingerprint();
        await authLinkCallback({ provider, code, state, error, fingerprint });
        if (!cancelled) {
          router.replace("/profile?tab=accounts" as Route);
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
  }, [provider, code, state, error, router]);

  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Linking account</h1>
      <p className="mt-3 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
        {message}
      </p>
    </main>
  );
}

