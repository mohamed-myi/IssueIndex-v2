"use client";

import type { Route } from "next";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  CircleDot,
  FileText,
  Github,
  Loader2,
  MessageSquareText,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/common/EmptyState";
import { useToast } from "@/components/common/Toast";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
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
  unlinkAccount,
} from "@/lib/api/endpoints";
import { useAuthGuard } from "@/lib/hooks/use-auth-guard";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TabId = "overview" | "onboarding" | "preferences" | "accounts" | "danger";

function toTabId(value: string): TabId {
  const allowed: TabId[] = ["overview", "onboarding", "preferences", "accounts", "danger"];
  return (allowed.includes(value as TabId) ? value : "overview") as TabId;
}

// Human-readable error messages from OAuth redirect error codes
const oauthErrorMessages: Record<string, string> = {
  consent_denied: "OAuth consent was denied.",
  csrf_failed: "Security validation failed. Please try again.",
  code_expired: "The authorization code has expired. Please try again.",
  email_not_verified: "Your email address is not verified with this provider.",
  existing_account: "An account with this email already exists under a different provider.",
  not_authenticated: "You must be signed in to perform this action.",
  provider_conflict: "This provider is already linked to another account.",
  no_email: "No email address was returned by the provider.",
  invalid_provider: "Invalid authentication provider.",
};


export default function ProfileClient(props: {
  initialTab: string;
  connected: string | null;
  initialError: string | null;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const { showToast, ToastContainer } = useToast();

  const [tab, setTab] = useState<TabId>(() => toTabId(props.initialTab));
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [unlinkDialogOpen, setUnlinkDialogOpen] = useState(false);
  const [unlinkProvider, setUnlinkProvider] = useState<string | null>(null);

  const { isRedirecting } = useAuthGuard();
  const meQuery = useQuery({ queryKey: ["auth", "me"], queryFn: fetchMe, retry: false });
  const profileQuery = useQuery({ queryKey: ["profile"], queryFn: fetchProfile, retry: false });
  const onboardingQuery = useQuery({
    queryKey: ["profile", "onboarding"],
    queryFn: fetchProfileOnboarding,
    retry: false,
  });
  const preferencesQuery = useQuery({
    queryKey: ["profile", "preferences"],
    queryFn: fetchPreferences,
    retry: false,
  });
  const accountsQuery = useQuery({
    queryKey: ["auth", "linked-accounts"],
    queryFn: fetchLinkedAccounts,
    retry: false,
  });

  // Show toast for URL-based feedback (OAuth redirect errors / success)
  useEffect(() => {
    if (props.initialError) {
      const msg = oauthErrorMessages[props.initialError] ?? `Authentication error: ${props.initialError}`;
      showToast(msg, "error");
    }
    if (props.connected === "github") {
      showToast("GitHub connected successfully.", "success");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Mutations 

  const startOnboardingMutation = useMutation({
    mutationFn: startOnboarding,
    onSuccess: async () => {
      showToast("Onboarding started.", "success");
      await qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
      goToTab("onboarding");
    },
    onError: (e) => showToast(getApiErrorMessage(e), "error"),
  });

  const skipOnboardingMutation = useMutation({
    mutationFn: skipOnboarding,
    onSuccess: async () => {
      showToast("Onboarding skipped. You can restart it anytime.", "info");
      await qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
      await qc.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e) => showToast(getApiErrorMessage(e), "error"),
  });

  const completeOnboardingMutation = useMutation({
    mutationFn: completeOnboarding,
    onSuccess: async () => {
      showToast("Onboarding completed! Your personalized feed is ready.", "success");
      await qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
      await qc.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (e) => showToast(getApiErrorMessage(e), "error"),
  });

  const patchPreferencesMutation = useMutation({
    mutationFn: patchPreferences,
    onSuccess: async () => {
      showToast("Preferences updated.", "success");
      await qc.invalidateQueries({ queryKey: ["profile", "preferences"] });
    },
    onError: (e) => showToast(getApiErrorMessage(e), "error"),
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["auth", "me"] });
      router.replace("/login");
    },
    onError: (e) => showToast(getApiErrorMessage(e), "error"),
  });

  const logoutAllMutation = useMutation({
    mutationFn: logoutAll,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["auth", "me"] });
      router.replace("/login");
    },
    onError: (e) => showToast(getApiErrorMessage(e), "error"),
  });

  const deleteAccountMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: async () => {
      await qc.invalidateQueries();
      router.replace("/");
    },
    onError: (e) => {
      setDeleteDialogOpen(false);
      showToast(getApiErrorMessage(e), "error");
    },
  });

  const unlinkAccountMutation = useMutation({
    mutationFn: (provider: string) => unlinkAccount(provider),
    onSuccess: async () => {
      showToast("Account unlinked successfully.", "success");
      setUnlinkDialogOpen(false);
      setUnlinkProvider(null);
      await qc.invalidateQueries({ queryKey: ["auth", "linked-accounts"] });
      await qc.invalidateQueries({ queryKey: ["auth", "me"] });
    },
    onError: (e) => {
      setUnlinkDialogOpen(false);
      setUnlinkProvider(null);
      showToast(getApiErrorMessage(e), "error");
    },
  });

  // Derived state 

  const isAuthed = meQuery.isSuccess;

  const base = getApiBaseUrl();
  const linkGithubUrl = `${base}/auth/link/github`;
  const linkGoogleUrl = `${base}/auth/link/google`;
  const connectGithubUrl = `${base}/auth/connect/github`;

  const goToTab = useCallback(
    (next: TabId) => {
      setTab(next);
      router.replace(`/profile?tab=${next}` as Route);
    },
    [router],
  );

  const overview = useMemo(() => {
    const p = profileQuery.data;
    if (!p) return null;
    return {
      optimization: p.optimization_percent,
      onboarding: p.onboarding_status,
      calculating: p.is_calculating,
    };
  }, [profileQuery.data]);

  // Determine which providers the user already has linked for login
  const createdVia = meQuery.data?.created_via ?? null;
  const hasGithubLogin = !!meQuery.data?.github_username;
  const hasGoogleLogin = !!meQuery.data?.google_id;

  if (isRedirecting) return null;

  // Render 

  return (
    <AppShell activeTab={null}>
      {/* Header */}
      <div className="mb-6">
        <div
          className="text-xs font-semibold uppercase tracking-widest"
          style={{ color: "#71717a" }}
        >
          Profile
        </div>
        <h1 className="mt-2 text-xl font-semibold tracking-tight">Your account</h1>
        <div className="mt-2 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
          {isAuthed ? `Signed in as ${meQuery.data.email}` : "Not signed in"}
        </div>
      </div>

      {!isAuthed ? (
        <EmptyState
          title="Sign in required"
          description={
            getApiErrorMessage(meQuery.error) + " — go to Login to continue."
          }
        />
      ) : (
        <>
          {/* Toast area */}
          <ToastContainer />

          {/* Tab bar */}
          <div className="mb-6 flex flex-wrap gap-2">
            {(
              [
                ["overview", "Overview"],
                ["onboarding", "Onboarding"],
                ["preferences", "Preferences"],
                ["accounts", "Accounts"],
                ["danger", "Account Deletion"],
              ] as [TabId, string][]
            ).map(([id, label]) => (
              <TabButton key={id} active={tab === id} onClick={() => goToTab(id)}>
                {label}
              </TabButton>
            ))}
          </div>

          {/* Overview tab */}
          {tab === "overview" && (
            <Section title="Overview">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard
                  label="Optimization"
                  value={overview ? `${overview.optimization}%` : "—"}
                  description="Profile completeness score. Intent contributes 50%, resume 30%, and GitHub 20%."
                />
                <StatCard
                  label="Onboarding"
                  value={overview ? formatStatus(overview.onboarding) : "—"}
                  description="Your onboarding status. Complete onboarding to unlock personalized recommendations."
                  statusColor={statusColor(overview?.onboarding ?? null)}
                />
                <StatCard
                  label="Calculating"
                  value={
                    overview
                      ? overview.calculating
                        ? "In progress"
                        : "Idle"
                      : "—"
                  }
                  description="Whether the system is currently computing your recommendation vectors."
                />
              </div>

              <div
                className="mt-6 pt-6"
                style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
              >
                <div className="text-sm font-semibold mb-1">Session</div>
                <div
                  className="mb-3 text-xs"
                  style={{ color: "rgba(138,144,178,1)" }}
                >
                  Manage your active sessions across devices.
                </div>
                <div className="flex flex-wrap gap-2">
                  <ActionButton
                    onClick={() => logoutMutation.mutate()}
                    disabled={logoutMutation.isPending}
                  >
                    {logoutMutation.isPending ? "Logging out..." : "Log out"}
                  </ActionButton>
                  <ActionButton
                    onClick={() => logoutAllMutation.mutate()}
                    disabled={logoutAllMutation.isPending}
                  >
                    {logoutAllMutation.isPending
                      ? "Logging out..."
                      : "Log out on all devices"}
                  </ActionButton>
                </div>
              </div>
            </Section>
          )}

          {/* Onboarding tab */}
          {tab === "onboarding" && (
            <div className="space-y-4">
              {/* Hero */}
              <Section title="Personalize Your Feed">
                <div
                  className="rounded-xl p-4 mb-4"
                  style={{
                    background:
                      "linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(138, 92, 255, 0.04))",
                    border: "1px solid rgba(99, 102, 241, 0.15)",
                  }}
                >
                  <div className="flex items-start gap-3">
                    <Sparkles
                      className="mt-0.5 h-5 w-5 flex-shrink-0"
                      style={{ color: "rgba(138, 92, 255, 0.95)" }}
                    />
                    <div>
                      <div
                        className="text-sm font-semibold"
                        style={{ color: "rgba(230,233,242,0.95)" }}
                      >
                        Build your developer profile to get personalized issue
                        recommendations
                      </div>
                      <div
                        className="mt-1 text-xs leading-relaxed"
                        style={{ color: "rgba(138,144,178,1)" }}
                      >
                        Add at least one source below to unlock your personalized
                        feed. Each source generates a vector that powers
                        recommendations matched to your skills and interests.
                      </div>
                    </div>
                  </div>
                </div>

                {/* Status badge */}
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-xs font-medium" style={{ color: "rgba(138,144,178,1)" }}>
                    Status:
                  </span>
                  <StatusBadge status={onboardingQuery.data?.status ?? "not_started"} />
                </div>

                {/* Progress checklist */}
                {onboardingQuery.data && (
                  <div className="mb-4 space-y-1.5">
                    {[
                      { id: "welcome", label: "Welcome" },
                      { id: "intent", label: "Intent profile" },
                      { id: "github", label: "GitHub connected" },
                      { id: "resume", label: "Resume uploaded" },
                      { id: "preferences", label: "Preferences set" },
                    ].map((step) => {
                      const done =
                        onboardingQuery.data.completed_steps.includes(step.id);
                      return (
                        <div
                          key={step.id}
                          className="flex items-center gap-2 text-xs"
                        >
                          {done ? (
                            <Check
                              className="h-3.5 w-3.5"
                              style={{ color: "rgba(34, 197, 94, 1)" }}
                            />
                          ) : (
                            <CircleDot
                              className="h-3.5 w-3.5"
                              style={{ color: "rgba(113,113,122,0.6)" }}
                            />
                          )}
                          <span
                            style={{
                              color: done
                                ? "rgba(230,233,242,0.95)"
                                : "rgba(138,144,178,0.8)",
                            }}
                          >
                            {step.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Section>

              {/* Source cards */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <SourceCard
                  icon={<MessageSquareText className="h-5 w-5" />}
                  title="Intent"
                  weight="50%"
                  description="Tell us your preferred languages, stack areas, and what kind of projects interest you."
                  completed={onboardingQuery.data?.completed_steps.includes("intent") ?? false}
                  actionLabel="Set intent"
                  onAction={() => goToTab("preferences")}
                />
                <SourceCard
                  icon={<FileText className="h-5 w-5" />}
                  title="Resume"
                  weight="30%"
                  description="Upload your resume to automatically extract skills and job titles via AI parsing."
                  completed={onboardingQuery.data?.completed_steps.includes("resume") ?? false}
                  actionLabel="Upload resume"
                  note="PDF or DOCX, max 5 MB"
                />
                <SourceCard
                  icon={<Github className="h-5 w-5" />}
                  title="GitHub"
                  weight="20%"
                  description="Connect your GitHub to analyze starred repos and contributions for skill signals."
                  completed={onboardingQuery.data?.completed_steps.includes("github") ?? false}
                  actionLabel="Connect GitHub"
                  href={connectGithubUrl}
                />
              </div>

              {/* Action buttons */}
              <Section title="Finalize">
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      if (onboardingQuery.data?.status === "not_started") {
                        startOnboardingMutation.mutate();
                      }
                      completeOnboardingMutation.mutate();
                    }}
                    disabled={
                      completeOnboardingMutation.isPending ||
                      !onboardingQuery.data?.can_complete
                    }
                    className="rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors disabled:opacity-40"
                    style={{
                      backgroundColor: onboardingQuery.data?.can_complete
                        ? "rgba(99, 102, 241, 0.7)"
                        : "rgba(99, 102, 241, 0.15)",
                      border: "1px solid rgba(99, 102, 241, 0.5)",
                      color: "rgba(255,255,255,0.95)",
                    }}
                  >
                    {completeOnboardingMutation.isPending ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Completing...
                      </span>
                    ) : (
                      "Complete Onboarding"
                    )}
                  </button>

                  {!onboardingQuery.data?.can_complete && (
                    <span
                      className="text-xs"
                      style={{ color: "rgba(138,144,178,0.7)" }}
                    >
                      Add at least one source (intent, resume, or GitHub) to
                      enable completion.
                    </span>
                  )}
                </div>

                <div className="mt-3">
                  <button
                    type="button"
                    onClick={() => skipOnboardingMutation.mutate()}
                    disabled={skipOnboardingMutation.isPending}
                    className="text-xs font-medium transition-colors hover:underline"
                    style={{ color: "rgba(138,144,178,0.8)" }}
                  >
                    {skipOnboardingMutation.isPending
                      ? "Skipping..."
                      : "Skip for now"}
                  </button>
                </div>
              </Section>
            </div>
          )}

          {/* Preferences tab */}
          {tab === "preferences" && (
            <Section title="Preferences">
              <div className="text-sm" style={{ color: "rgba(138,144,178,1)" }}>
                These preferences control how your feed is filtered. They work
                alongside your profile vectors for more precise recommendations.
              </div>

              <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <InputCard
                  key={`languages-${preferencesQuery.dataUpdatedAt}`}
                  label="Preferred languages"
                  description="Programming languages to prioritize in your feed. Used as an exact-match filter in the first retrieval stage."
                  placeholder="e.g. Python, TypeScript, Rust"
                  value={(preferencesQuery.data?.preferred_languages ?? []).join(
                    ", ",
                  )}
                  isSaving={patchPreferencesMutation.isPending}
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
                  label="Preferred topics"
                  description="Topic areas to boost in recommendations. These expand your results beyond exact language matches."
                  placeholder="e.g. machine-learning, web, cli"
                  value={(preferencesQuery.data?.preferred_topics ?? []).join(
                    ", ",
                  )}
                  isSaving={patchPreferencesMutation.isPending}
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
                  label="Min heat threshold"
                  description="Quality floor for recommendations. 0.0 shows all issues, 1.0 only the most active. Default is 0.6."
                  placeholder="0.6"
                  value={String(
                    preferencesQuery.data?.min_heat_threshold ?? 0.6,
                  )}
                  isSaving={patchPreferencesMutation.isPending}
                  onSave={(value) =>
                    patchPreferencesMutation.mutate({
                      min_heat_threshold: Number(value),
                    })
                  }
                />
              </div>
            </Section>
          )}

          {/* Accounts tab */}
          {tab === "accounts" && (
            <Section title="Linked accounts">
              <div
                className="text-sm mb-4"
                style={{ color: "rgba(138,144,178,1)" }}
              >
                Link additional login methods to your account. You can sign in
                with any linked provider.
              </div>

              {/* Link buttons - hide if already authenticated via that provider */}
              <div className="mb-5 flex flex-wrap gap-2">
                {!hasGithubLogin && (
                  <a
                    className="rounded-xl border px-4 py-2 text-sm font-medium transition-colors hover:bg-white/5"
                    style={{ borderColor: "rgba(255,255,255,0.10)" }}
                    href={linkGithubUrl}
                  >
                    Link GitHub login
                  </a>
                )}
                {!hasGoogleLogin && (
                  <a
                    className="rounded-xl border px-4 py-2 text-sm font-medium transition-colors hover:bg-white/5"
                    style={{ borderColor: "rgba(255,255,255,0.10)" }}
                    href={linkGoogleUrl}
                  >
                    Link Google login
                  </a>
                )}
                {hasGithubLogin && hasGoogleLogin && (
                  <div
                    className="text-xs"
                    style={{ color: "rgba(138,144,178,0.7)" }}
                  >
                    All available providers are linked.
                  </div>
                )}
              </div>

              {/* Connected accounts list */}
              {accountsQuery.isError ? (
                <EmptyState
                  title="Unable to load linked accounts"
                  description={getApiErrorMessage(accountsQuery.error)}
                />
              ) : (
                <div className="space-y-3">
                  {/* Always show GitHub row */}
                  <AccountCard
                    provider="github"
                    providerLabel="GitHub"
                    connected={hasGithubLogin}
                    username={meQuery.data?.github_username ?? null}
                    isPrimary={createdVia === "github"}
                    onUnlink={() => {
                      setUnlinkProvider("github");
                      setUnlinkDialogOpen(true);
                    }}
                  />
                  {/* Always show Google row */}
                  <AccountCard
                    provider="google"
                    providerLabel="Google"
                    connected={hasGoogleLogin}
                    username={meQuery.data?.email ?? null}
                    isPrimary={createdVia === "google"}
                    onUnlink={() => {
                      setUnlinkProvider("google");
                      setUnlinkDialogOpen(true);
                    }}
                  />
                </div>
              )}

              {/* Unlink confirmation dialog */}
              <ConfirmDialog
                open={unlinkDialogOpen}
                onOpenChange={setUnlinkDialogOpen}
                title={`Unlink ${unlinkProvider ?? "provider"}?`}
                description={`You will no longer be able to sign in with ${unlinkProvider ?? "this provider"}. You can re-link it later from this page.`}
                confirmLabel="Unlink"
                variant="danger"
                isPending={unlinkAccountMutation.isPending}
                onConfirm={() => {
                  if (unlinkProvider) unlinkAccountMutation.mutate(unlinkProvider);
                }}
              />
            </Section>
          )}

          {/* Danger zone tab */}
          {tab === "danger" && (
            <Section title="Danger Zone">
              <div className="text-sm" style={{ color: "rgba(138,144,178,1)" }}>
                This permanently deletes your account and all associated data.
                This action is irreversible and compliant with GDPR data
                deletion requirements.
              </div>

              <div className="mt-4 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
                The following will be permanently deleted:
              </div>
              <ul
                className="mt-2 space-y-1 text-sm list-disc list-inside"
                style={{ color: "rgba(138,144,178,0.8)" }}
              >
                <li>Your user profile and all profile vectors</li>
                <li>Intent, resume, and GitHub profile data</li>
                <li>Feed preferences and recommendation history</li>
                <li>All linked OAuth accounts and tokens</li>
                <li>Saved bookmarks and notes</li>
                <li>All active sessions</li>
              </ul>

              <div className="mt-6 flex justify-end">
                <button
                  type="button"
                  className="rounded-xl border px-5 py-2.5 text-sm font-semibold transition-colors hover:brightness-110"
                  style={{
                    backgroundColor: "rgba(220, 38, 38, 0.8)",
                    borderColor: "rgba(220, 38, 38, 0.5)",
                    color: "rgba(255, 255, 255, 0.95)",
                  }}
                  onClick={() => setDeleteDialogOpen(true)}
                  disabled={deleteAccountMutation.isPending}
                >
                  {deleteAccountMutation.isPending ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Deleting...
                    </span>
                  ) : (
                    "Delete account"
                  )}
                </button>
              </div>

              {/* Delete confirmation dialog */}
              <ConfirmDialog
                open={deleteDialogOpen}
                onOpenChange={setDeleteDialogOpen}
                title="Delete your account?"
                description="This will permanently delete your account and all associated data. This cannot be undone."
                confirmLabel="Delete my account"
                variant="danger"
                requiredConfirmText="DELETE"
                isPending={deleteAccountMutation.isPending}
                onConfirm={() => deleteAccountMutation.mutate()}
              />
            </Section>
          )}
        </>
      )}
    </AppShell>
  );
}

  // Sub-components

function Section(props: { title: string; children: React.ReactNode }) {
  return (
    <div
      className="rounded-2xl border p-6"
      style={{
        borderColor: "rgba(255,255,255,0.08)",
        backgroundColor: "rgba(24, 24, 27, 0.35)",
      }}
    >
      <div className="text-sm font-semibold">{props.title}</div>
      <div className="mt-4">{props.children}</div>
    </div>
  );
}

function TabButton(props: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className="rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors"
      style={{
        backgroundColor: props.active
          ? "rgba(99, 102, 241, 0.15)"
          : "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.08)",
        color: props.active
          ? "rgba(255,255,255,0.95)"
          : "rgba(255,255,255,0.70)",
      }}
    >
      {props.children}
    </button>
  );
}

function ActionButton(props: {
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      disabled={props.disabled}
      className="rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-50 transition-colors"
      style={{
        backgroundColor: "rgba(99, 102, 241, 0.15)",
        border: "1px solid rgba(99, 102, 241, 0.35)",
      }}
    >
      {props.children}
    </button>
  );
}

function StatCard(props: {
  label: string;
  value: string;
  description: string;
  statusColor?: string;
}) {
  return (
    <div
      className="rounded-2xl border px-4 py-3"
      style={{
        borderColor: "rgba(255,255,255,0.08)",
        backgroundColor: "rgba(24, 24, 27, 0.25)",
      }}
    >
      <div
        className="text-[11px] font-semibold uppercase tracking-widest"
        style={{ color: "#71717a" }}
      >
        {props.label}
      </div>
      <div
        className="mt-2 text-xl font-semibold tracking-tight"
        style={{ color: props.statusColor ?? "rgba(230,233,242,0.95)" }}
      >
        {props.value}
      </div>
      <div
        className="mt-2 text-[11px] leading-relaxed"
        style={{ color: "rgba(138,144,178,0.7)" }}
      >
        {props.description}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color = statusColor(status);
  const bg = statusBg(status);
  return (
    <span
      className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
      style={{ color, backgroundColor: bg }}
    >
      {formatStatus(status)}
    </span>
  );
}

function SourceCard(props: {
  icon: React.ReactNode;
  title: string;
  weight: string;
  description: string;
  completed: boolean;
  actionLabel: string;
  onAction?: () => void;
  href?: string;
  note?: string;
}) {
  const content = (
    <div
      className="rounded-2xl border p-5 h-full flex flex-col"
      style={{
        borderColor: props.completed
          ? "rgba(34, 197, 94, 0.2)"
          : "rgba(255,255,255,0.08)",
        backgroundColor: props.completed
          ? "rgba(34, 197, 94, 0.04)"
          : "rgba(24, 24, 27, 0.35)",
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span style={{ color: "rgba(138, 92, 255, 0.9)" }}>{props.icon}</span>
          <span
            className="text-sm font-semibold"
            style={{ color: "rgba(230,233,242,0.95)" }}
          >
            {props.title}
          </span>
        </div>
        <span
          className="rounded-full px-2 py-0.5 text-[10px] font-bold"
          style={{
            backgroundColor: "rgba(99, 102, 241, 0.12)",
            color: "rgba(165, 180, 252, 1)",
          }}
        >
          {props.weight}
        </span>
      </div>

      <div
        className="text-xs leading-relaxed flex-1"
        style={{ color: "rgba(138,144,178,1)" }}
      >
        {props.description}
      </div>

      {props.note && (
        <div
          className="mt-2 text-[10px]"
          style={{ color: "rgba(138,144,178,0.6)" }}
        >
          {props.note}
        </div>
      )}

      <div className="mt-3">
        {props.completed ? (
          <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "rgba(34, 197, 94, 1)" }}>
            <Check className="h-3.5 w-3.5" />
            Completed
          </div>
        ) : props.href ? (
          <a
            href={props.href}
            className="inline-block rounded-xl px-3 py-1.5 text-xs font-medium transition-colors hover:bg-white/5"
            style={{
              backgroundColor: "rgba(99, 102, 241, 0.15)",
              border: "1px solid rgba(99, 102, 241, 0.35)",
              color: "rgba(255,255,255,0.9)",
            }}
          >
            {props.actionLabel}
          </a>
        ) : props.onAction ? (
          <button
            type="button"
            onClick={props.onAction}
            className="rounded-xl px-3 py-1.5 text-xs font-medium transition-colors hover:bg-white/5"
            style={{
              backgroundColor: "rgba(99, 102, 241, 0.15)",
              border: "1px solid rgba(99, 102, 241, 0.35)",
              color: "rgba(255,255,255,0.9)",
            }}
          >
            {props.actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  );

  return content;
}

function AccountCard(props: {
  provider: string;
  providerLabel: string;
  connected: boolean;
  username: string | null;
  isPrimary: boolean;
  onUnlink: () => void;
}) {
  return (
    <div
      className="rounded-2xl border p-4 flex items-center justify-between"
      style={{
        borderColor: "rgba(255,255,255,0.08)",
        backgroundColor: "rgba(24, 24, 27, 0.35)",
      }}
    >
      <div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{props.providerLabel}</span>
          {props.isPrimary && (
            <span
              className="rounded-full px-2 py-0.5 text-[10px] font-bold"
              style={{
                backgroundColor: "rgba(99, 102, 241, 0.15)",
                color: "rgba(165, 180, 252, 1)",
              }}
            >
              Primary login
            </span>
          )}
        </div>
        <div
          className="mt-1 text-sm"
          style={{ color: "rgba(138,144,178,1)" }}
        >
          {props.connected
            ? `Connected as ${props.username ?? "—"}`
            : "Not connected"}
        </div>
      </div>

      {props.connected && !props.isPrimary && (
        <button
          type="button"
          onClick={props.onUnlink}
          className="rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-white/5"
          style={{
            borderColor: "rgba(220, 38, 38, 0.3)",
            color: "rgba(248, 113, 113, 1)",
          }}
        >
          Unlink
        </button>
      )}
    </div>
  );
}

function InputCard(props: {
  label: string;
  description: string;
  placeholder: string;
  value: string;
  isSaving: boolean;
  onSave: (value: string) => void;
}) {
  const [value, setValue] = useState(props.value);
  const [isDirty, setIsDirty] = useState(false);

  return (
    <div
      className="rounded-2xl border p-4 flex flex-col"
      style={{
        borderColor: "rgba(255,255,255,0.08)",
        backgroundColor: "rgba(24, 24, 27, 0.25)",
      }}
    >
      <div
        className="text-xs font-semibold"
        style={{ color: "rgba(230,233,242,0.95)" }}
      >
        {props.label}
      </div>
      <div
        className="mt-1 text-[11px] leading-relaxed"
        style={{ color: "rgba(138,144,178,0.7)" }}
      >
        {props.description}
      </div>
      <input
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setIsDirty(true);
        }}
        placeholder={props.placeholder}
        className="mt-3 w-full rounded-xl border bg-transparent px-3 py-2 text-sm outline-none placeholder:text-white/20"
        style={{
          borderColor: "rgba(255,255,255,0.10)",
          color: "rgba(230,233,242,0.95)",
        }}
      />
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={() => {
            props.onSave(value);
            setIsDirty(false);
          }}
          disabled={!isDirty || props.isSaving}
          className="rounded-xl px-3 py-1.5 text-xs font-medium disabled:opacity-40 transition-colors"
          style={{
            backgroundColor: "rgba(99, 102, 241, 0.15)",
            border: "1px solid rgba(99, 102, 241, 0.35)",
          }}
        >
          {props.isSaving ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}

// Helpers

function formatStatus(status: string): string {
  const map: Record<string, string> = {
    not_started: "Not started",
    in_progress: "In progress",
    completed: "Completed",
    skipped: "Skipped",
  };
  return map[status] ?? status;
}

function statusColor(status: string | null): string {
  if (!status) return "rgba(230,233,242,0.95)";
  const map: Record<string, string> = {
    not_started: "rgba(138,144,178,1)",
    in_progress: "rgba(250, 204, 21, 1)",
    completed: "rgba(34, 197, 94, 1)",
    skipped: "rgba(138,144,178,0.7)",
  };
  return map[status] ?? "rgba(230,233,242,0.95)";
}

function statusBg(status: string): string {
  const map: Record<string, string> = {
    not_started: "rgba(138,144,178,0.12)",
    in_progress: "rgba(250, 204, 21, 0.12)",
    completed: "rgba(34, 197, 94, 0.12)",
    skipped: "rgba(138,144,178,0.08)",
  };
  return map[status] ?? "rgba(138,144,178,0.12)";
}
