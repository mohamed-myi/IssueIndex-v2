"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PropsWithChildren, useState, useEffect } from "react";

export function Providers({ children }: PropsWithChildren) {
  const [queryClient] = useState(() => new QueryClient());
  
  // Track whether MSW is ready (or not needed)
  const [mockReady, setMockReady] = useState(
    process.env.NEXT_PUBLIC_MOCK_API !== "true"
  );

  useEffect(() => {
    // Only initialize MSW when mock API is enabled
    if (process.env.NEXT_PUBLIC_MOCK_API === "true") {
      import("@/mocks").then(({ initMocks }) => {
        initMocks().then(() => setMockReady(true));
      });
    }
  }, []);

  // Wait for MSW to initialize before rendering anything
  // This prevents race conditions where requests fire before MSW is ready
  if (!mockReady) {
    return null;
  }

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
