export async function initMocks() {
  // Only run in browser
  if (typeof window === "undefined") {
    return;
  }

  // Only run when mock API is enabled
  if (process.env.NEXT_PUBLIC_MOCK_API !== "true") {
    return;
  }

  // Dynamic import to avoid bundling in production
  const { worker } = await import("./browser");

  await worker.start({
    onUnhandledRequest: "bypass", // Let unhandled requests pass through
    quiet: false, // Show MSW logs in console
  });

  console.log("[MSW] Mock API enabled - all requests will be intercepted");
}
