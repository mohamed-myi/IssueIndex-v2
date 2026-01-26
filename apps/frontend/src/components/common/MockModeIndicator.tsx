"use client";

export function MockModeIndicator() {
  // Only show in mock mode
  if (process.env.NEXT_PUBLIC_MOCK_API !== "true") {
    return null;
  }

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold shadow-lg"
      style={{
        backgroundColor: "rgba(234, 179, 8, 0.95)",
        color: "#1a1a1a",
      }}
    >
      <span
        className="w-2 h-2 rounded-full animate-pulse"
        style={{ backgroundColor: "#dc2626" }}
      />
      MOCK MODE
    </div>
  );
}
