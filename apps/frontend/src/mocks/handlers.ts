import { http, HttpResponse } from "msw";
import {
  mockIssues,
  getMockIssueDetail,
  filterMockIssues,
  getSimilarIssues,
  mockUser,
  mockProfile,
  mockPreferences,
  mockLinkedAccounts,
  mockSessions,
  getOnboardingStatus,
  startOnboardingMock,
  skipOnboardingMock,
  completeOnboardingMock,
  getBookmarks,
  getBookmarkById,
  checkBookmarks,
  createBookmark,
  deleteBookmark,
  updateBookmark,
  getNotes,
  addNote,
  updateNote,
  deleteNote,
  filterRepositories,
  mockLanguages,
  mockStackAreas,
} from "./data/index";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const handlers = [
  // Public Stats
  http.get(`${BASE_URL}/stats`, () => {
    return HttpResponse.json({
      total_issues: 12847,
      total_repos: 423,
      total_languages: 32,
      indexed_at: new Date().toISOString(),
    });
  }),

  // Feed & Trending
  http.get(`${BASE_URL}/feed/trending`, ({ request }) => {
    const url = new URL(request.url);
    const page = Number(url.searchParams.get("page")) || 1;
    const pageSize = Number(url.searchParams.get("page_size")) || 10;
    const languages = url.searchParams.getAll("languages");
    const labels = url.searchParams.getAll("labels");
    const repos = url.searchParams.getAll("repos");

    // Apply filters
    let filtered = mockIssues;
    if (languages.length > 0) {
      filtered = filtered.filter((issue) => languages.includes(issue.primary_language));
    }
    if (labels.length > 0) {
      filtered = filtered.filter((issue) => 
        issue.labels.some((label) => labels.includes(label))
      );
    }
    if (repos.length > 0) {
      filtered = filtered.filter((issue) => repos.includes(issue.repo_name));
    }

    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const results = filtered.slice(start, end).map((issue) => ({
      node_id: issue.node_id,
      title: issue.title,
      body_preview: issue.body_preview,
      github_url: issue.github_url,
      labels: issue.labels,
      q_score: issue.q_score,
      repo_name: issue.repo_name,
      primary_language: issue.primary_language,
      github_created_at: issue.github_created_at,
    }));

    return HttpResponse.json({
      results,
      total: filtered.length,
      page,
      page_size: pageSize,
      has_more: end < filtered.length,
    });
  }),

  http.get(`${BASE_URL}/feed`, ({ request }) => {
    const url = new URL(request.url);
    const page = Number(url.searchParams.get("page")) || 1;
    const pageSize = Number(url.searchParams.get("page_size")) || 20;
    const languages = url.searchParams.getAll("languages");
    const labels = url.searchParams.getAll("labels");
    const repos = url.searchParams.getAll("repos");

    // Apply filters
    let filtered = mockIssues;
    if (languages.length > 0) {
      filtered = filtered.filter((issue) => languages.includes(issue.primary_language));
    }
    if (labels.length > 0) {
      filtered = filtered.filter((issue) => 
        issue.labels.some((label) => labels.includes(label))
      );
    }
    if (repos.length > 0) {
      filtered = filtered.filter((issue) => repos.includes(issue.repo_name));
    }

    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const results = filtered.slice(start, end).map((issue) => ({
      node_id: issue.node_id,
      title: issue.title,
      body_preview: issue.body_preview,
      github_url: issue.github_url,
      labels: issue.labels,
      q_score: issue.q_score,
      repo_name: issue.repo_name,
      primary_language: issue.primary_language,
      github_created_at: issue.github_created_at,
      similarity_score: Math.random() * 0.3 + 0.6,
      why_this: [
        { entity: "TypeScript", score: 0.85 },
        { entity: "React", score: 0.72 },
      ],
    }));

    return HttpResponse.json({
      results,
      total: filtered.length,
      page,
      page_size: pageSize,
      has_more: end < filtered.length,
      is_personalized: true,
      profile_cta: null,
      recommendation_batch_id: `mock-batch-${Date.now()}`,
    });
  }),

  // Search
  http.post(`${BASE_URL}/search`, async ({ request }) => {
    const body = (await request.json()) as {
      query: string;
      filters?: { languages?: string[]; labels?: string[]; repos?: string[] };
      page?: number;
      page_size?: number;
    };

    const results = filterMockIssues(body.query, body.filters);
    const page = body.page || 1;
    const pageSize = body.page_size || 20;
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const pagedResults = results.slice(start, end);

    return HttpResponse.json({
      search_id: `search_${Date.now()}`,
      results: pagedResults,
      total: results.length,
      page,
      page_size: pageSize,
      has_more: end < results.length,
    });
  }),

  http.post(`${BASE_URL}/search/interact`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${BASE_URL}/recommendations/events`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Issues
  http.get(`${BASE_URL}/issues/:nodeId`, ({ params }) => {
    const nodeId = decodeURIComponent(params.nodeId as string);
    const issue = getMockIssueDetail(nodeId);

    if (!issue) {
      return HttpResponse.json({ detail: "Issue not found" }, { status: 404 });
    }

    return HttpResponse.json(issue);
  }),

  http.get(`${BASE_URL}/issues/:nodeId/similar`, ({ params, request }) => {
    const nodeId = decodeURIComponent(params.nodeId as string);
    const url = new URL(request.url);
    const limit = Number(url.searchParams.get("limit")) || 5;

    const issues = getSimilarIssues(nodeId, limit);

    return HttpResponse.json({ issues });
  }),

  // Taxonomy
  http.get(`${BASE_URL}/taxonomy/languages`, () => {
    return HttpResponse.json(mockLanguages);
  }),

  http.get(`${BASE_URL}/taxonomy/stack-areas`, () => {
    return HttpResponse.json(mockStackAreas);
  }),

  // Repositories
  http.get(`${BASE_URL}/repositories`, ({ request }) => {
    const url = new URL(request.url);
    const q = url.searchParams.get("q") || undefined;
    const language = url.searchParams.get("language") || undefined;
    const limit = url.searchParams.get("limit")
      ? Number(url.searchParams.get("limit"))
      : undefined;

    const repositories = filterRepositories({ q, language, limit });

    return HttpResponse.json({ repositories });
  }),

  // Auth

  // OAuth login redirect - simulates the OAuth flow by redirecting to callback
  http.get(`${BASE_URL}/auth/login/:provider`, ({ params, request }) => {
    const provider = params.provider as string;
    const url = new URL(request.url);

    // Build callback URL that mimics what OAuth provider would redirect to
    const origin = url.origin.replace(BASE_URL, "http://localhost:3000");
    const callbackUrl = new URL(`/auth/callback/${provider}`, origin);
    callbackUrl.searchParams.set("code", "mock_auth_code_12345");
    callbackUrl.searchParams.set("state", "mock_state_xyz");

    return HttpResponse.redirect(callbackUrl.toString(), 302);
  }),

  http.get(`${BASE_URL}/auth/init`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  http.get(`${BASE_URL}/auth/me`, () => {
    return HttpResponse.json(mockUser);
  }),

  http.get(`${BASE_URL}/auth/sessions`, () => {
    return HttpResponse.json(mockSessions);
  }),

  http.delete(`${BASE_URL}/auth/sessions/:sessionId`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  http.delete(`${BASE_URL}/auth/sessions`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  http.get(`${BASE_URL}/auth/linked-accounts`, () => {
    return HttpResponse.json(mockLinkedAccounts);
  }),

  http.post(`${BASE_URL}/auth/logout`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  http.post(`${BASE_URL}/auth/logout/all`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  http.delete(`${BASE_URL}/auth/account`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  // OAuth callbacks - just return success for mocks
  http.get(`${BASE_URL}/auth/callback/:provider`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  http.get(`${BASE_URL}/auth/link/callback/:provider`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  http.get(`${BASE_URL}/auth/connect/callback/github`, () => {
    return HttpResponse.json({ status: "ok" });
  }),

  // Profile
  http.get(`${BASE_URL}/profile`, () => {
    return HttpResponse.json(mockProfile);
  }),

  http.get(`${BASE_URL}/profile/onboarding`, () => {
    return HttpResponse.json(getOnboardingStatus());
  }),

  http.post(`${BASE_URL}/profile/onboarding/start`, () => {
    return HttpResponse.json(startOnboardingMock());
  }),

  http.post(`${BASE_URL}/profile/onboarding/skip`, () => {
    return HttpResponse.json(skipOnboardingMock());
  }),

  http.post(`${BASE_URL}/profile/onboarding/complete`, () => {
    return HttpResponse.json(completeOnboardingMock());
  }),

  http.patch(`${BASE_URL}/profile/onboarding/step/:step`, async ({ params }) => {
    const step = params.step as string;
    return HttpResponse.json({
      ...getOnboardingStatus(),
      step,
      payload: {},
    });
  }),

  http.post(`${BASE_URL}/profile/resume`, () => {
    return HttpResponse.json(
      { job_id: `resume_job_${Date.now()}`, status: "processing", message: "Resume processing started." },
      { status: 202 },
    );
  }),

  http.get(`${BASE_URL}/profile/resume`, () => {
    return HttpResponse.json({
      status: "ready",
      skills: ["TypeScript", "React", "Python"],
      job_titles: ["Software Engineer"],
      vector_status: "ready",
      uploaded_at: new Date().toISOString(),
    });
  }),

  http.post(`${BASE_URL}/profile/github`, () => {
    return HttpResponse.json(
      { job_id: `github_job_${Date.now()}`, status: "processing", message: "GitHub sync started." },
      { status: 202 },
    );
  }),

  http.get(`${BASE_URL}/profile/github`, () => {
    return HttpResponse.json({
      status: "ready",
      username: mockUser.github_username ?? "mock-user",
      starred_count: 42,
      contributed_repos: 12,
      languages: ["TypeScript", "Python"],
      topics: ["web", "api"],
      vector_status: "ready",
      fetched_at: new Date().toISOString(),
    });
  }),

  http.get(`${BASE_URL}/profile/preferences`, () => {
    return HttpResponse.json(mockPreferences);
  }),

  http.patch(`${BASE_URL}/profile/preferences`, async ({ request }) => {
    const updates = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      ...mockPreferences,
      ...updates,
    });
  }),

  // Bookmarks
  http.get(`${BASE_URL}/bookmarks`, ({ request }) => {
    const url = new URL(request.url);
    const page = Number(url.searchParams.get("page")) || 1;
    const pageSize = Number(url.searchParams.get("page_size")) || 20;

    const allBookmarks = getBookmarks();
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const results = allBookmarks.slice(start, end);

    return HttpResponse.json({
      results,
      total: allBookmarks.length,
      page,
      page_size: pageSize,
      has_more: end < allBookmarks.length,
    });
  }),

  http.post(`${BASE_URL}/bookmarks`, async ({ request }) => {
    const body = (await request.json()) as {
      issue_node_id: string;
      github_url: string;
      title_snapshot: string;
      body_snapshot: string;
    };

    const bookmark = createBookmark(body);
    return HttpResponse.json(bookmark, { status: 201 });
  }),

  http.get(`${BASE_URL}/bookmarks/:bookmarkId`, ({ params }) => {
    const bookmarkId = params.bookmarkId as string;
    const bookmark = getBookmarkById(bookmarkId);

    if (!bookmark) {
      return HttpResponse.json({ detail: "Bookmark not found" }, { status: 404 });
    }

    return HttpResponse.json(bookmark);
  }),

  http.patch(`${BASE_URL}/bookmarks/:bookmarkId`, async ({ params, request }) => {
    const bookmarkId = params.bookmarkId as string;
    const body = (await request.json()) as { is_resolved?: boolean };

    const bookmark = updateBookmark(bookmarkId, body);

    if (!bookmark) {
      return HttpResponse.json({ detail: "Bookmark not found" }, { status: 404 });
    }

    return HttpResponse.json(bookmark);
  }),

  http.delete(`${BASE_URL}/bookmarks/:bookmarkId`, ({ params }) => {
    const bookmarkId = params.bookmarkId as string;
    const deleted = deleteBookmark(bookmarkId);

    if (!deleted) {
      return HttpResponse.json({ detail: "Bookmark not found" }, { status: 404 });
    }

    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${BASE_URL}/bookmarks/check`, async ({ request }) => {
    const body = (await request.json()) as { issue_node_ids: string[] };
    const bookmarks = checkBookmarks(body.issue_node_ids);

    return HttpResponse.json({ bookmarks });
  }),

  // Notes
  http.get(`${BASE_URL}/bookmarks/:bookmarkId/notes`, ({ params }) => {
    const bookmarkId = params.bookmarkId as string;
    const notes = getNotes(bookmarkId);

    return HttpResponse.json({ results: notes });
  }),

  http.post(`${BASE_URL}/bookmarks/:bookmarkId/notes`, async ({ params, request }) => {
    const bookmarkId = params.bookmarkId as string;
    const body = (await request.json()) as { content: string };

    const note = addNote(bookmarkId, body.content);
    return HttpResponse.json(note, { status: 201 });
  }),

  http.patch(`${BASE_URL}/bookmarks/notes/:noteId`, async ({ params, request }) => {
    const noteId = params.noteId as string;
    const body = (await request.json()) as { content: string };

    const note = updateNote(noteId, body.content);

    if (!note) {
      return HttpResponse.json({ detail: "Note not found" }, { status: 404 });
    }

    return HttpResponse.json(note);
  }),

  http.delete(`${BASE_URL}/bookmarks/notes/:noteId`, ({ params }) => {
    const noteId = params.noteId as string;
    const deleted = deleteNote(noteId);

    if (!deleted) {
      return HttpResponse.json({ detail: "Note not found" }, { status: 404 });
    }

    return new HttpResponse(null, { status: 204 });
  }),
];
