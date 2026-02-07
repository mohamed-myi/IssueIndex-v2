"use client";

import type { Route } from "next";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/common/EmptyState";
import { getApiBaseUrl } from "@/lib/api/base-url";
import { getApiErrorMessage } from "@/lib/api/client";
import {
  completeOnboarding,
  deleteAccount,
  fetchLinkedAccounts,
  fetchMe,
  fetchPreferences,
  fetchProfile,
  fetchProfileOnboarding,
  logout,
  logoutAll,
  patchPreferences,
  skipOnboarding,
  startOnboarding,
} from "@/lib/api/endpoints";
import { useAuthGuard } from "@/lib/hooks/use-auth-guard";

type TabId = "overview" | "onboarding" | "preferences" | "accounts" | "danger";

function toTabId(value: string): TabId {
  const allowed: TabId[] = ["overview", "onboarding", "preferences", "accounts", "danger"];
  return (allowed.includes(value as TabId) ? value : "overview") as TabId;
}

export default function ProfileClient(props: { initialTab: string; connected: string | null }) {
  const router = useRouter();
  const qc = useQueryClient();

  const [tab, setTab] = useState<TabId>(() => toTabId(props.initialTab));
  const [toast, setToast] = useState<string | null>(null);

  const { isRedirecting } = useAuthGuard();
  const meQuery = useQuery({ queryKey: ["auth", "me"], queryFn: fetchMe, retry: false });
  const profileQuery = useQuery({ queryKey: ["profile"], queryFn: fetchProfile, retry: false });
  const onboardingQuery = useQuery({ queryKey: ["profile", "onboarding"], queryFn: fetchProfileOnboarding, retry: false });
  const preferencesQuery = useQuery({ queryKey: ["profile", "preferences"], queryFn: fetchPreferences, retry: false });
  const accountsQuery = useQuery({ queryKey: ["auth", "linked-accounts"], queryFn: fetchLinkedAccounts, retry: false });

  const startOnboardingMutation = useMutation({
    mutationFn: startOnboarding,
    onSuccess: async () => {
      setToast("Onboarding started.");
      await qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
      goToTab("onboarding");
    },
    onError: (e) => setToast(getApiErrorMessage(e)),
  });

  const skipOnboardingMutation = useMutation({
    mutationFn: skipOnboarding,
    onSuccess: async () => {
      setToast("Onboarding skipped.");
      await qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
    },
    onError: (e) => setToast(getApiErrorMessage(e)),
  });

  const completeOnboardingMutation = useMutation({
    mutationFn: completeOnboarding,
    onSuccess: async () => {
      setToast("Onboarding completed.");
      await qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
      await qc.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e) => setToast(getApiErrorMessage(e)),
  });

  const patchPreferencesMutation = useMutation({
    mutationFn: patchPreferences,
    onSuccess: async () => {
      setToast("Preferences updated.");
      await qc.invalidateQueries({ queryKey: ["profile", "preferences"] });
    },
    onError: (e) => setToast(getApiErrorMessage(e)),
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      setToast("Logged out.");
      await qc.invalidateQueries({ queryKey: ["auth", "me"] });
      router.replace("/login");
    },
    onError: (e) => setToast(getApiErrorMessage(e)),
  });

  const logoutAllMutation = useMutation({
    mutationFn: logoutAll,
    onSuccess: async () => {
      setToast("Logged out everywhere.");
      await qc.invalidateQueries({ queryKey: ["auth", "me"] });
      router.replace("/login");
    },
    onError: (e) => setToast(getApiErrorMessage(e)),
  });

  const deleteAccountMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: async () => {
      setToast("Account deleted.");
      await qc.invalidateQueries();
      router.replace("/");
    },
    onError: (e) => setToast(getApiErrorMessage(e)),
  });

  const isAuthed = meQuery.isSuccess;

  const base = getApiBaseUrl();
  const linkGithubUrl = `${base}/auth/link/github`;
  const linkGoogleUrl = `${base}/auth/link/google`;
  const connectGithubUrl = `${base}/auth/connect/github`;

  function goToTab(next: TabId) {
    setTab(next);
    router.replace(`/profile?tab=${next}` as Route);
  }

  const overview = useMemo(() => {
    const p = profileQuery.data;
    if (!p) return null;
    return {
      optimization: p.optimization_percent,
      onboarding: p.onboarding_status,
      calculating: p.is_calculating,
    };
  }, [profileQuery.data]);

  if (isRedirecting) return null;

  return (
    <AppShell activeTab={null}>
      <div className="mb-6">
        <div className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#71717a" }}>
          Profile
        </div>
        <h1 className="mt-2 text-xl font-semibold tracking-tight">Your account</h1>
        <div className="mt-2 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
          {isAuthed ? `Signed in as ${meQuery.data.email}` : "Not signed in"}
        </div>
      </div>

      {!isAuthed ? (
        <EmptyState title="Sign in required" description={getApiErrorMessage(meQuery.error) + " — go to Login to continue."} />
      ) : (
        <>
          {toast ? (
            <div
              className="mb-6 rounded-xl border px-4 py-3 text-sm"
              style={{ borderColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(24, 24, 27, 0.35)" }}
            >
              {toast}
            </div>
          ) : null}

          <div className="mb-6 flex flex-wrap gap-2">
            <TabButton active={tab === "overview"} onClick={() => goToTab("overview")}>
              Overview
            </TabButton>
            <TabButton active={tab === "onboarding"} onClick={() => goToTab("onboarding")}>
              Onboarding
            </TabButton>
            <TabButton active={tab === "preferences"} onClick={() => goToTab("preferences")}>
              Preferences
            </TabButton>
            <TabButton active={tab === "accounts"} onClick={() => goToTab("accounts")}>
              Accounts
            </TabButton>
            <TabButton active={tab === "danger"} onClick={() => goToTab("danger")}>
              Account Deletion
            </TabButton>
          </div>

          {tab === "overview" ? (
            <Section title="Overview">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Stat label="Optimization" value={overview ? `${overview.optimization}%` : "—"} />
                <Stat label="Onboarding" value={overview ? overview.onboarding : "—"} />
                <Stat label="Calculating" value={overview ? (overview.calculating ? "yes" : "no") : "—"} />
              </div>

              <div className="mt-6 pt-6" style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                <div className="text-sm font-semibold mb-3">Session</div>
                <div className="flex flex-wrap gap-2">
                  <ActionButton onClick={() => logoutMutation.mutate()} disabled={logoutMutation.isPending}>
                    Log out
                  </ActionButton>
                  <ActionButton onClick={() => logoutAllMutation.mutate()} disabled={logoutAllMutation.isPending}>
                    Log out on all devices
                  </ActionButton>
                </div>
              </div>
            </Section>
          ) : null}

          {tab === "onboarding" ? (
            <Section title="Onboarding">
              {props.connected === "github" ? (
                <div className="mb-3 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
                  GitHub connected.
                </div>
              ) : null}

              <div className="mb-4 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
                Status: <span style={{ color: "rgba(230,233,242,0.95)" }}>{onboardingQuery.data?.status ?? "—"}</span>
              </div>

              <div className="flex flex-wrap gap-2">
                <ActionButton onClick={() => startOnboardingMutation.mutate()} disabled={startOnboardingMutation.isPending}>
                  Start / restart
                </ActionButton>
                <ActionButton onClick={() => skipOnboardingMutation.mutate()} disabled={skipOnboardingMutation.isPending}>
                  Skip
                </ActionButton>
                <ActionButton
                  onClick={() => completeOnboardingMutation.mutate()}
                  disabled={completeOnboardingMutation.isPending || !onboardingQuery.data?.can_complete}
                >
                  Complete
                </ActionButton>
              </div>

              <div className="mt-6">
                <div className="text-sm font-semibold">Connect sources</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <a className={linkClassName} href={connectGithubUrl}>
                    Connect GitHub (profile access)
                  </a>
                  <Link className={linkClassName} href={"/profile?tab=preferences" as Route}>
                    Set preferences
                  </Link>
                </div>
              </div>
            </Section>
          ) : null}

          {tab === "preferences" ? (
            <Section title="Preferences">
              <div className="text-sm" style={{ color: "rgba(138,144,178,1)" }}>
                This controls feed filtering on the backend.
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <InputCard
                  key={`languages-${preferencesQuery.dataUpdatedAt}`}
                  label="Preferred languages (comma-separated)"
                  value={(preferencesQuery.data?.preferred_languages ?? []).join(", ")}
                  onSave={(value) =>
                    patchPreferencesMutation.mutate({
                      preferred_languages: value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
                <InputCard
                  key={`topics-${preferencesQuery.dataUpdatedAt}`}
                  label="Preferred topics (comma-separated)"
                  value={(preferencesQuery.data?.preferred_topics ?? []).join(", ")}
                  onSave={(value) =>
                    patchPreferencesMutation.mutate({
                      preferred_topics: value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
                <InputCard
                  key={`heat-${preferencesQuery.dataUpdatedAt}`}
                  label="Min heat threshold (0.0 - 1.0)"
                  value={String(preferencesQuery.data?.min_heat_threshold ?? 0.6)}
                  onSave={(value) =>
                    patchPreferencesMutation.mutate({
                      min_heat_threshold: Number(value),
                    })
                  }
                />
              </div>
            </Section>
          ) : null}

          {tab === "accounts" ? (
            <Section title="Linked accounts">
              <div className="mb-4 flex flex-wrap gap-2">
                <a className={linkClassName} href={linkGithubUrl}>
                  Link GitHub login
                </a>
                <a className={linkClassName} href={linkGoogleUrl}>
                  Link Google login
                </a>
              </div>

              {accountsQuery.isError ? (
                <EmptyState title="Unable to load linked accounts" description={getApiErrorMessage(accountsQuery.error)} />
              ) : (
                <div className="space-y-3">
                  {(accountsQuery.data?.accounts ?? []).map((acct) => (
                    <div
                      key={acct.provider}
                      className="rounded-2xl border p-4"
                      style={{ borderColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(24, 24, 27, 0.35)" }}
                    >
                      <div className="text-sm font-semibold">{acct.provider}</div>
                      <div className="mt-1 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
                        {acct.connected ? `Connected as ${acct.username ?? "—"}` : "Not connected"}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          ) : null}

          {tab === "danger" ? (
            <Section title="Account Deletion">
              <div className="text-sm" style={{ color: "rgba(138,144,178,1)" }}>
                This action permanently deletes your account and associated data.
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-white/5 transition-colors"
                  style={{ borderColor: "rgba(255,255,255,0.10)", backgroundColor: "rgba(212, 24, 61, 0.12)" }}
                  onClick={() => deleteAccountMutation.mutate()}
                  disabled={deleteAccountMutation.isPending}
                >
                  Delete account
                </button>
              </div>
            </Section>
          ) : null}
        </>
      )}
    </AppShell>
  );
}

const linkClassName =
  "rounded-xl border px-4 py-2 text-sm font-medium hover:bg-white/5 transition-colors";

function Section(props: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border p-6" style={{ borderColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(24, 24, 27, 0.35)" }}>
      <div className="text-sm font-semibold">{props.title}</div>
      <div className="mt-4">{props.children}</div>
    </div>
  );
}

function TabButton(props: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className="rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors"
      style={{
        backgroundColor: props.active ? "rgba(99, 102, 241, 0.15)" : "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.08)",
        color: props.active ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.70)",
      }}
    >
      {props.children}
    </button>
  );
}

function ActionButton(props: { onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      disabled={props.disabled}
      className="rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-50"
      style={{
        backgroundColor: "rgba(99, 102, 241, 0.15)",
        border: "1px solid rgba(99, 102, 241, 0.35)",
      }}
    >
      {props.children}
    </button>
  );
}

function Stat(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border px-4 py-3" style={{ borderColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(24, 24, 27, 0.25)" }}>
      <div className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: "#71717a" }}>
        {props.label}
      </div>
      <div className="mt-2 text-xl font-semibold tracking-tight" style={{ color: "rgba(230,233,242,0.95)" }}>
        {props.value}
      </div>
    </div>
  );
}

function InputCard(props: { label: string; value: string; onSave: (value: string) => void }) {
  const [value, setValue] = useState(props.value);
  const [isDirty, setIsDirty] = useState(false);

  return (
    <div className="rounded-2xl border p-4" style={{ borderColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(24, 24, 27, 0.25)" }}>
      <div className="text-xs font-semibold" style={{ color: "rgba(138,144,178,1)" }}>
        {props.label}
      </div>
      <input
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setIsDirty(true);
        }}
        className="mt-2 w-full rounded-xl border bg-transparent px-3 py-2 text-sm outline-none"
        style={{ borderColor: "rgba(255,255,255,0.10)", color: "rgba(230,233,242,0.95)" }}
      />
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={() => {
            props.onSave(value);
            setIsDirty(false);
          }}
          disabled={!isDirty}
          className="rounded-xl px-3 py-1.5 text-xs font-medium disabled:opacity-50"
          style={{ backgroundColor: "rgba(99, 102, 241, 0.15)", border: "1px solid rgba(99, 102, 241, 0.35)" }}
        >
          Save
        </button>
      </div>
    </div>
  );
}
