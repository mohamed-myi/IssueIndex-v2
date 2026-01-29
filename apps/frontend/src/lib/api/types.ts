export type ApiErrorPayload = {
  detail: string;
};

export type OAuthProvider = "github" | "google";

export type TaxonomyLanguagesResponse = {
  languages: string[];
};

export type TaxonomyStackAreasResponse = {
  stack_areas: Array<{
    id: string;
    label: string;
    description: string;
  }>;
};

export type PublicStatsResponse = {
  total_issues: number;
  total_repos: number;
  total_languages: number;
  indexed_at: string;
};

export type FeedIssue = {
  node_id: string;
  title: string;
  body_preview: string;
  labels: string[];
  q_score: number;
  repo_name: string;
  primary_language: string;
  github_created_at: string;
  similarity_score?: number | null;
  why_this?: Array<{ entity: string; score: number }> | null;
};

export type FeedResponse = {
  results: FeedIssue[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  is_personalized: boolean;
  profile_cta: string | null;
};

export type TrendingResponse = {
  results: Array<Omit<FeedIssue, "similarity_score" | "why_this">>;
  total: number;
  limit: number;
};

export type SearchRequest = {
  query: string;
  filters?: {
    languages?: string[];
    labels?: string[];
    repos?: string[];
  };
  page?: number;
  page_size?: number;
};

export type SearchResult = {
  node_id: string;
  title: string;
  body_preview: string;
  labels: string[];
  q_score: number;
  repo_name: string;
  primary_language: string;
  github_created_at: string;
  rrf_score: number;
};

export type SearchResponse = {
  search_id: string;
  results: SearchResult[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
};

export type IssueDetailResponse = {
  node_id: string;
  title: string;
  body: string;
  labels: string[];
  q_score: number;
  repo_name: string;
  repo_url: string;
  github_url: string;
  primary_language: string;
  github_created_at: string;
  state: "open" | "closed";
};

export type SimilarIssuesResponse = {
  issues: Array<{
    node_id: string;
    title: string;
    repo_name: string;
    similarity_score: number;
  }>;
};

export type RepositoriesResponse = {
  repositories: Array<{
    name: string;
    primary_language: string;
    issue_count: number;
  }>;
};

export type Bookmark = {
  id: string;
  issue_node_id: string;
  github_url: string;
  title_snapshot: string;
  body_snapshot: string;
  is_resolved: boolean;
  created_at: string;
  notes_count: number;
};

export type BookmarksListResponse = {
  results: Bookmark[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
};

export type BookmarkCheckResponse = {
  bookmarked: boolean;
  bookmark_id: string | null;
};

export type BookmarkBatchCheckResponse = {
  bookmarks: Record<string, string | null>;
};

export type Note = {
  id: string;
  bookmark_id: string;
  content: string;
  updated_at: string;
};

export type NotesListResponse = {
  results: Note[];
};

export type AuthMeResponse = {
  id: string;
  email: string;
  github_username: string | null;
  google_id: string | null;
  created_at: string;
  created_via: string;
};

export type ProfileResponse = {
  user_id: string;
  optimization_percent: number;
  combined_vector_status: "ready" | "processing" | null;
  is_calculating: boolean;
  onboarding_status: "not_started" | "in_progress" | "completed" | "skipped";
  updated_at: string;
  sources: Record<
    "intent" | "resume" | "github",
    {
      populated: boolean;
      vector_status: "ready" | "processing" | null;
      data: unknown;
    }
  >;
  preferences: {
    preferred_languages: string[];
    preferred_topics: string[];
    min_heat_threshold: number;
  };
};

export type ProfileOnboardingResponse = {
  status: "not_started" | "in_progress" | "completed" | "skipped";
  completed_steps: string[];
  available_steps: string[];
  can_complete: boolean;
};

export type ProfilePreferences = {
  preferred_languages: string[];
  preferred_topics: string[];
  min_heat_threshold: number;
};

export type ProfilePreferencesResponse = ProfilePreferences;

export type LinkedAccount = {
  provider: string;
  connected: boolean;
  username: string | null;
  connected_at: string | null;
  scopes: string[] | null;
};

export type LinkedAccountsResponse = {
  accounts: LinkedAccount[];
};

export type SessionInfo = {
  id: string;
  fingerprint_partial: string;
  created_at: string;
  last_active_at: string;
  user_agent: string;
  ip_address: string;
  is_current: boolean;
};

export type SessionsResponse = {
  sessions: SessionInfo[];
  count: number;
};

export type OnboardingStep = "welcome" | "intent" | "preferences";

export type OnboardingStepResponse = {
  status: ProfileOnboardingResponse["status"];
  completed_steps: string[];
  available_steps: string[];
  can_complete: boolean;
  step: OnboardingStep;
  payload: unknown;
};

