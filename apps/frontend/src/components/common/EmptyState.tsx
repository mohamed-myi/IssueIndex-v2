"use client";

export function EmptyState(props: { title?: string; description?: string }) {
  const title = props.title ?? "No results";
  const description = props.description ?? "Try adjusting your search or filters.";

  return (
    <div
      className="rounded-2xl border p-10"
      style={{
        borderColor: "rgba(255,255,255,0.08)",
        backgroundColor: "rgba(24, 24, 27, 0.35)",
      }}
    >
      <div className="text-base font-semibold" style={{ color: "rgba(230,233,242,0.95)" }}>
        {title}
      </div>
      <div className="mt-2 text-sm" style={{ color: "rgba(138,144,178,1)" }}>
        {description}
      </div>
    </div>
  );
}

