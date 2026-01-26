import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPublicStats,
  fetchTrending,
  fetchFeed,
  searchIssues,
  fetchIssue,
  fetchSimilarIssues,
  fetchRepositories,
  fetchLanguages,
  fetchStackAreas,
  fetchMe,
  listBookmarks,
  getBookmark,
  createBookmark,
  deleteBookmark,
  patchBookmark,
  batchBookmarkCheck,
  listNotes,
  addNote,
  updateNote,
  deleteNote,
  fetchProfile,
  fetchProfileOnboarding,
  fetchPreferences,
  patchPreferences,
  fetchLinkedAccounts,
  fetchSessions,
  startOnboarding,
  skipOnboarding,
  completeOnboarding,
  saveOnboardingStep,
} from "./endpoints";
import type { SearchRequest, ProfilePreferences, OnboardingStep } from "./types";

// ============================================================================
// Public / Stats
// ============================================================================

export function usePublicStats() {
  return useQuery({
    queryKey: ["public", "stats"],
    queryFn: fetchPublicStats,
    staleTime: 1000 * 60,
  });
}

// ============================================================================
// Feed & Search
// ============================================================================

export function useTrending(limit = 10) {
  return useQuery({
    queryKey: ["feed", "trending", limit],
    queryFn: () => fetchTrending(limit),
    staleTime: 1000 * 30,
  });
}

export function useFeed(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["feed", page, pageSize],
    queryFn: () => fetchFeed(page, pageSize),
    staleTime: 1000 * 30,
  });
}

export function useSearch(params: {
  query: string;
  filters?: SearchRequest["filters"];
  page?: number;
  pageSize?: number;
  enabled?: boolean;
}) {
  const { query, filters, page = 1, pageSize = 20, enabled = true } = params;

  return useQuery({
    queryKey: ["search", query, filters, page, pageSize],
    queryFn: () =>
      searchIssues({
        query,
        filters,
        page,
        page_size: pageSize,
      }),
    enabled: enabled && query.trim().length > 0,
    retry: false,
  });
}

// ============================================================================
// Issues
// ============================================================================

export function useIssue(nodeId: string | null) {
  return useQuery({
    queryKey: ["issue", nodeId],
    queryFn: () => fetchIssue(nodeId!),
    enabled: !!nodeId,
    staleTime: 1000 * 60 * 5,
  });
}

export function useSimilarIssues(nodeId: string | null, limit = 5) {
  return useQuery({
    queryKey: ["issue", nodeId, "similar", limit],
    queryFn: () => fetchSimilarIssues(nodeId!, limit),
    enabled: !!nodeId,
    staleTime: 1000 * 60,
  });
}

// ============================================================================
// Repositories & Taxonomy
// ============================================================================

export function useRepositories(params: { q?: string; language?: string; limit?: number } = {}) {
  return useQuery({
    queryKey: ["repositories", params],
    queryFn: () => fetchRepositories(params),
    staleTime: 1000 * 60 * 5,
  });
}

export function useLanguages() {
  return useQuery({
    queryKey: ["taxonomy", "languages"],
    queryFn: fetchLanguages,
    staleTime: 1000 * 60 * 60,
  });
}

export function useStackAreas() {
  return useQuery({
    queryKey: ["taxonomy", "stack-areas"],
    queryFn: fetchStackAreas,
    staleTime: 1000 * 60 * 60,
  });
}

// ============================================================================
// Bookmarks
// ============================================================================

export function useBookmarks(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["bookmarks", page, pageSize],
    queryFn: () => listBookmarks(page, pageSize),
    staleTime: 1000 * 10,
  });
}

export function useBookmark(bookmarkId: string | null) {
  return useQuery({
    queryKey: ["bookmark", bookmarkId],
    queryFn: () => getBookmark(bookmarkId!),
    enabled: !!bookmarkId,
    staleTime: 1000 * 60,
  });
}

export function useBookmarkCheck(issueNodeIds: string[]) {
  return useQuery({
    queryKey: ["bookmarks", "check", issueNodeIds],
    queryFn: () => batchBookmarkCheck(issueNodeIds),
    enabled: issueNodeIds.length > 0,
    staleTime: 1000 * 30,
  });
}

export function useCreateBookmark() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: createBookmark,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bookmarks"] });
    },
  });
}

export function useDeleteBookmark() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: deleteBookmark,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bookmarks"] });
    },
  });
}

export function usePatchBookmark() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ bookmarkId, isResolved }: { bookmarkId: string; isResolved: boolean }) =>
      patchBookmark(bookmarkId, { is_resolved: isResolved }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bookmarks"] });
    },
  });
}

// ============================================================================
// Notes
// ============================================================================

export function useNotes(bookmarkId: string | null) {
  return useQuery({
    queryKey: ["bookmark", bookmarkId, "notes"],
    queryFn: () => listNotes(bookmarkId!),
    enabled: !!bookmarkId,
    staleTime: 1000 * 30,
  });
}

export function useAddNote() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ bookmarkId, content }: { bookmarkId: string; content: string }) =>
      addNote(bookmarkId, content),
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: ["bookmark", variables.bookmarkId, "notes"] });
    },
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ noteId, content }: { noteId: string; content: string }) =>
      updateNote(noteId, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bookmark"] });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: deleteNote,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bookmark"] });
    },
  });
}

// ============================================================================
// Auth
// ============================================================================

export function useMe() {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: fetchMe,
    retry: false,
    staleTime: 1000 * 60,
  });
}

export function useSessions() {
  return useQuery({
    queryKey: ["auth", "sessions"],
    queryFn: fetchSessions,
    retry: false,
    staleTime: 1000 * 30,
  });
}

export function useLinkedAccounts() {
  return useQuery({
    queryKey: ["auth", "linked-accounts"],
    queryFn: fetchLinkedAccounts,
    retry: false,
    staleTime: 1000 * 60,
  });
}

// ============================================================================
// Profile
// ============================================================================

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: fetchProfile,
    retry: false,
    staleTime: 1000 * 30,
  });
}

export function useOnboarding() {
  return useQuery({
    queryKey: ["profile", "onboarding"],
    queryFn: fetchProfileOnboarding,
    retry: false,
    staleTime: 1000 * 30,
  });
}

export function usePreferences() {
  return useQuery({
    queryKey: ["profile", "preferences"],
    queryFn: fetchPreferences,
    retry: false,
    staleTime: 1000 * 30,
  });
}

export function usePatchPreferences() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: (payload: Partial<ProfilePreferences>) => patchPreferences(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile", "preferences"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}

export function useStartOnboarding() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: startOnboarding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
    },
  });
}

export function useSkipOnboarding() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: skipOnboarding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
    },
  });
}

export function useCompleteOnboarding() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: completeOnboarding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}

export function useSaveOnboardingStep() {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ step, payload }: { step: OnboardingStep; payload: unknown }) =>
      saveOnboardingStep(step, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile", "onboarding"] });
    },
  });
}
