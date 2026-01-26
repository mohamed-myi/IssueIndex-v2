"use client";

export function SkeletonList(props: { rows?: number }) {
  const rows = props.rows ?? 8;
  return (
    <div className="space-y-0">
      {Array.from({ length: rows }).map((_, idx) => (
        <div
          key={idx}
          className="animate-pulse px-5 py-4"
          style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}
        >
          <div className="mb-2 h-4 w-3/4 rounded" style={{ backgroundColor: "rgba(255, 255, 255, 0.06)" }} />
          <div className="h-3 w-1/3 rounded" style={{ backgroundColor: "rgba(255, 255, 255, 0.06)" }} />
        </div>
      ))}
    </div>
  );
}

