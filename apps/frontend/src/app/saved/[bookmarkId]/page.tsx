"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/common/EmptyState";
import { getApiErrorMessage } from "@/lib/api/client";
import { addNote, deleteNote, getBookmark, listNotes, updateNote } from "@/lib/api/endpoints";

export default function SavedDetailPage() {
  const params = useParams<{ bookmarkId: string }>();
  const bookmarkId = params.bookmarkId;

  const qc = useQueryClient();
  const [newNote, setNewNote] = useState("");

  const bookmarkQuery = useQuery({
    queryKey: ["bookmarks", bookmarkId],
    queryFn: () => getBookmark(bookmarkId),
    retry: false,
  });

  const notesQuery = useQuery({
    queryKey: ["bookmarks", bookmarkId, "notes"],
    queryFn: () => listNotes(bookmarkId),
    retry: false,
  });

  const createNote = useMutation({
    mutationFn: () => addNote(bookmarkId, newNote),
    onSuccess: async () => {
      setNewNote("");
      await qc.invalidateQueries({ queryKey: ["bookmarks", bookmarkId, "notes"] });
    },
  });

  const editNote = useMutation({
    mutationFn: (input: { noteId: string; content: string }) => updateNote(input.noteId, input.content),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["bookmarks", bookmarkId, "notes"] });
    },
  });

  const removeNote = useMutation({
    mutationFn: (noteId: string) => deleteNote(noteId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["bookmarks", bookmarkId, "notes"] });
    },
  });

  if (bookmarkQuery.isError) {
    return (
      <AppShell activeTab={null}>
        <EmptyState title="Unable to load bookmark" description={getApiErrorMessage(bookmarkQuery.error)} />
      </AppShell>
    );
  }

  const bookmark = bookmarkQuery.data;

  return (
    <AppShell activeTab={null}>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#71717a" }}>
            Saved
          </div>
          <h1 className="mt-2 text-xl font-semibold tracking-tight">{bookmark?.title_snapshot ?? "Loading…"}</h1>
          <div className="mt-2 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
            <Link className="underline underline-offset-2" href="/saved">
              Back to saved
            </Link>
          </div>
        </div>

        {bookmark?.github_url ? (
          <a
            href={bookmark.github_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-white/5 transition-colors"
            style={{ borderColor: "rgba(255,255,255,0.08)" }}
          >
            Open on GitHub
          </a>
        ) : null}
      </div>

      {bookmark?.body_snapshot ? (
        <div
          className="rounded-2xl border p-6"
          style={{ borderColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(24, 24, 27, 0.35)" }}
        >
          <div className="text-sm whitespace-pre-wrap" style={{ color: "rgba(138,144,178,1)" }}>
            {bookmark.body_snapshot}
          </div>
        </div>
      ) : null}

      <div className="mt-8">
        <div className="mb-3 text-sm font-semibold">Notes</div>

        {notesQuery.isError ? (
          <EmptyState title="Unable to load notes" description={getApiErrorMessage(notesQuery.error)} />
        ) : (
          <div className="space-y-3">
            {(notesQuery.data?.results ?? []).map((note) => (
              <NoteRow
                key={note.id}
                noteId={note.id}
                content={note.content}
                updatedAt={note.updated_at}
                onSave={(content) => editNote.mutate({ noteId: note.id, content })}
                onDelete={() => removeNote.mutate(note.id)}
              />
            ))}

            <div
              className="rounded-2xl border p-4"
              style={{ borderColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(24, 24, 27, 0.35)" }}
            >
              <textarea
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="Add a note…"
                className="min-h-[96px] w-full resize-y rounded-xl border bg-transparent p-3 text-sm outline-none"
                style={{ borderColor: "rgba(255,255,255,0.10)", color: "rgba(230,233,242,0.95)" }}
              />
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={() => createNote.mutate()}
                  disabled={!newNote.trim()}
                  className="rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-50"
                  style={{
                    backgroundColor: "rgba(99, 102, 241, 0.15)",
                    border: "1px solid rgba(99, 102, 241, 0.35)",
                  }}
                >
                  Add note
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function NoteRow(props: {
  noteId: string;
  content: string;
  updatedAt: string;
  onSave: (content: string) => void;
  onDelete: () => void;
}) {
  const [value, setValue] = useState(props.content);
  const [isDirty, setIsDirty] = useState(false);

  return (
    <div
      className="rounded-2xl border p-4"
      style={{ borderColor: "rgba(255,255,255,0.08)", backgroundColor: "rgba(24, 24, 27, 0.35)" }}
    >
      <textarea
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setIsDirty(true);
        }}
        className="min-h-[72px] w-full resize-y rounded-xl border bg-transparent p-3 text-sm outline-none"
        style={{ borderColor: "rgba(255,255,255,0.10)", color: "rgba(230,233,242,0.95)" }}
      />
      <div className="mt-3 flex items-center justify-between">
        <div className="text-xs" style={{ color: "rgba(138,144,178,1)" }}>
          Updated {new Date(props.updatedAt).toLocaleString()}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={props.onDelete}
            className="rounded-xl border px-3 py-1.5 text-xs font-medium hover:bg-white/5 transition-colors"
            style={{ borderColor: "rgba(255,255,255,0.08)" }}
          >
            Delete
          </button>
          <button
            type="button"
            onClick={() => {
              props.onSave(value);
              setIsDirty(false);
            }}
            disabled={!isDirty}
            className="rounded-xl px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            style={{
              backgroundColor: "rgba(99, 102, 241, 0.15)",
              border: "1px solid rgba(99, 102, 241, 0.35)",
            }}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

