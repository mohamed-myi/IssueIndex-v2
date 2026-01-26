import type { Bookmark, Note } from "@/lib/api/types";
import { mockIssues } from "./issues";

// Initial mock bookmarks based on some of the mock issues
const initialBookmarks: Bookmark[] = [
  {
    id: "bm_001",
    issue_node_id: mockIssues[0].node_id,
    github_url: mockIssues[0].github_url,
    title_snapshot: mockIssues[0].title,
    body_snapshot: mockIssues[0].body_preview,
    is_resolved: false,
    created_at: "2025-12-14T10:00:00Z",
    notes_count: 2,
  },
  {
    id: "bm_002",
    issue_node_id: mockIssues[2].node_id,
    github_url: mockIssues[2].github_url,
    title_snapshot: mockIssues[2].title,
    body_snapshot: mockIssues[2].body_preview,
    is_resolved: false,
    created_at: "2025-12-13T15:30:00Z",
    notes_count: 1,
  },
  {
    id: "bm_003",
    issue_node_id: mockIssues[5].node_id,
    github_url: mockIssues[5].github_url,
    title_snapshot: mockIssues[5].title,
    body_snapshot: mockIssues[5].body_preview,
    is_resolved: true,
    created_at: "2025-12-10T09:15:00Z",
    notes_count: 0,
  },
  {
    id: "bm_004",
    issue_node_id: mockIssues[7].node_id,
    github_url: mockIssues[7].github_url,
    title_snapshot: mockIssues[7].title,
    body_snapshot: mockIssues[7].body_preview,
    is_resolved: false,
    created_at: "2025-12-12T11:45:00Z",
    notes_count: 3,
  },
];

const initialNotes: Record<string, Note[]> = {
  bm_001: [
    {
      id: "note_001",
      bookmark_id: "bm_001",
      content: "This looks like a good first issue. I should look at the existing theme implementation first.",
      updated_at: "2025-12-14T10:30:00Z",
    },
    {
      id: "note_002",
      bookmark_id: "bm_001",
      content: "Found the theme context in src/contexts/ThemeContext.tsx - need to add dark mode CSS variables.",
      updated_at: "2025-12-14T14:00:00Z",
    },
  ],
  bm_002: [
    {
      id: "note_003",
      bookmark_id: "bm_002",
      content: "PKCE implementation reference: RFC 7636. Need to review existing auth flow first.",
      updated_at: "2025-12-13T16:00:00Z",
    },
  ],
  bm_004: [
    {
      id: "note_004",
      bookmark_id: "bm_004",
      content: "Interesting streaming problem. Should check how other frameworks handle this.",
      updated_at: "2025-12-12T12:00:00Z",
    },
    {
      id: "note_005",
      bookmark_id: "bm_004",
      content: "Transfer-Encoding: chunked is the way to go. Need to implement proper backpressure handling.",
      updated_at: "2025-12-12T15:30:00Z",
    },
    {
      id: "note_006",
      bookmark_id: "bm_004",
      content: "Found a good article: https://example.com/streaming-responses - bookmarking for later.",
      updated_at: "2025-12-13T09:00:00Z",
    },
  ],
};

// Mutable state for mock operations
let mockBookmarks: Bookmark[] = [...initialBookmarks];
let mockNotes: Record<string, Note[]> = JSON.parse(JSON.stringify(initialNotes));
let nextBookmarkId = 5;
let nextNoteId = 7;

export function getBookmarks(): Bookmark[] {
  return [...mockBookmarks];
}

export function getBookmarkById(id: string): Bookmark | undefined {
  return mockBookmarks.find((b) => b.id === id);
}

export function getBookmarkByIssueNodeId(issueNodeId: string): Bookmark | undefined {
  return mockBookmarks.find((b) => b.issue_node_id === issueNodeId);
}

export function checkBookmarks(issueNodeIds: string[]): Record<string, string | null> {
  const result: Record<string, string | null> = {};
  for (const nodeId of issueNodeIds) {
    const bookmark = getBookmarkByIssueNodeId(nodeId);
    result[nodeId] = bookmark ? bookmark.id : null;
  }
  return result;
}

export function createBookmark(input: {
  issue_node_id: string;
  github_url: string;
  title_snapshot: string;
  body_snapshot: string;
}): Bookmark {
  const existing = getBookmarkByIssueNodeId(input.issue_node_id);
  if (existing) return existing;

  const newBookmark: Bookmark = {
    id: `bm_${String(nextBookmarkId++).padStart(3, "0")}`,
    issue_node_id: input.issue_node_id,
    github_url: input.github_url,
    title_snapshot: input.title_snapshot,
    body_snapshot: input.body_snapshot,
    is_resolved: false,
    created_at: new Date().toISOString(),
    notes_count: 0,
  };

  mockBookmarks.unshift(newBookmark);
  mockNotes[newBookmark.id] = [];

  return newBookmark;
}

export function deleteBookmark(id: string): boolean {
  const index = mockBookmarks.findIndex((b) => b.id === id);
  if (index === -1) return false;

  mockBookmarks.splice(index, 1);
  delete mockNotes[id];

  return true;
}

export function updateBookmark(id: string, updates: { is_resolved?: boolean }): Bookmark | undefined {
  const bookmark = mockBookmarks.find((b) => b.id === id);
  if (!bookmark) return undefined;

  if (updates.is_resolved !== undefined) {
    bookmark.is_resolved = updates.is_resolved;
  }

  return bookmark;
}

export function getNotes(bookmarkId: string): Note[] {
  return mockNotes[bookmarkId] || [];
}

export function addNote(bookmarkId: string, content: string): Note {
  const note: Note = {
    id: `note_${String(nextNoteId++).padStart(3, "0")}`,
    bookmark_id: bookmarkId,
    content,
    updated_at: new Date().toISOString(),
  };

  if (!mockNotes[bookmarkId]) {
    mockNotes[bookmarkId] = [];
  }
  mockNotes[bookmarkId].push(note);

  const bookmark = mockBookmarks.find((b) => b.id === bookmarkId);
  if (bookmark) {
    bookmark.notes_count++;
  }

  return note;
}

export function updateNote(noteId: string, content: string): Note | undefined {
  for (const notes of Object.values(mockNotes)) {
    const note = notes.find((n) => n.id === noteId);
    if (note) {
      note.content = content;
      note.updated_at = new Date().toISOString();
      return note;
    }
  }
  return undefined;
}

export function deleteNote(noteId: string): boolean {
  for (const [bookmarkId, notes] of Object.entries(mockNotes)) {
    const index = notes.findIndex((n) => n.id === noteId);
    if (index !== -1) {
      notes.splice(index, 1);
      const bookmark = mockBookmarks.find((b) => b.id === bookmarkId);
      if (bookmark && bookmark.notes_count > 0) {
        bookmark.notes_count--;
      }
      return true;
    }
  }
  return false;
}

// Reset function for testing
export function resetBookmarks() {
  mockBookmarks = [...initialBookmarks];
  mockNotes = JSON.parse(JSON.stringify(initialNotes));
  nextBookmarkId = 5;
  nextNoteId = 7;
}
