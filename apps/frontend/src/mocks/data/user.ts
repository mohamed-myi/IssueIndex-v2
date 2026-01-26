import type {
  AuthMeResponse,
  ProfileResponse,
  ProfileOnboardingResponse,
  ProfilePreferencesResponse,
  LinkedAccountsResponse,
  SessionsResponse,
} from "@/lib/api/types";

export const mockUser: AuthMeResponse = {
  id: "usr_mock_12345",
  email: "developer@example.com",
  github_username: "mockdev",
  google_id: null,
  created_at: "2025-01-01T00:00:00Z",
  created_via: "github",
};

export const mockProfile: ProfileResponse = {
  user_id: "usr_mock_12345",
  optimization_percent: 75,
  combined_vector_status: "ready",
  is_calculating: false,
  onboarding_status: "completed",
  updated_at: "2025-12-15T10:00:00Z",
  sources: {
    intent: {
      populated: true,
      vector_status: "ready",
      data: {
        goals: ["Learn new technologies", "Contribute to OSS"],
        experience_level: "intermediate",
      },
    },
    resume: {
      populated: true,
      vector_status: "ready",
      data: {
        years_experience: 5,
        skills: ["TypeScript", "React", "Node.js", "Python"],
      },
    },
    github: {
      populated: true,
      vector_status: "ready",
      data: {
        top_languages: ["TypeScript", "JavaScript", "Python"],
        contribution_count: 342,
      },
    },
  },
  preferences: {
    preferred_languages: ["TypeScript", "JavaScript", "Python"],
    preferred_topics: ["web development", "api design", "testing"],
    min_heat_threshold: 0.6,
  },
};

export const mockOnboarding: ProfileOnboardingResponse = {
  status: "completed",
  completed_steps: ["welcome", "intent", "preferences"],
  available_steps: ["welcome", "intent", "preferences"],
  can_complete: true,
};

export const mockPreferences: ProfilePreferencesResponse = {
  preferred_languages: ["TypeScript", "JavaScript", "Python"],
  preferred_topics: ["web development", "api design", "testing"],
  min_heat_threshold: 0.6,
};

export const mockLinkedAccounts: LinkedAccountsResponse = {
  accounts: [
    {
      provider: "github",
      connected: true,
      username: "mockdev",
      connected_at: "2025-01-01T00:00:00Z",
      scopes: ["read:user", "user:email"],
    },
    {
      provider: "google",
      connected: false,
      username: null,
      connected_at: null,
      scopes: null,
    },
  ],
};

export const mockSessions: SessionsResponse = {
  sessions: [
    {
      id: "sess_current_123",
      fingerprint_partial: "abc123...xyz",
      created_at: "2025-12-10T08:00:00Z",
      last_active_at: new Date().toISOString(),
      user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
      ip_address: "192.168.1.100",
      is_current: true,
    },
    {
      id: "sess_old_456",
      fingerprint_partial: "def456...uvw",
      created_at: "2025-12-05T14:30:00Z",
      last_active_at: "2025-12-08T16:45:00Z",
      user_agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1",
      ip_address: "10.0.0.50",
      is_current: false,
    },
  ],
  count: 2,
};

// Mutable state for mock operations
let currentOnboardingStatus = mockOnboarding.status;

export function getOnboardingStatus(): ProfileOnboardingResponse {
  return {
    ...mockOnboarding,
    status: currentOnboardingStatus,
  };
}

export function startOnboardingMock(): ProfileOnboardingResponse {
  currentOnboardingStatus = "in_progress";
  return getOnboardingStatus();
}

export function skipOnboardingMock(): ProfileOnboardingResponse {
  currentOnboardingStatus = "skipped";
  return getOnboardingStatus();
}

export function completeOnboardingMock(): ProfileOnboardingResponse {
  currentOnboardingStatus = "completed";
  return getOnboardingStatus();
}
