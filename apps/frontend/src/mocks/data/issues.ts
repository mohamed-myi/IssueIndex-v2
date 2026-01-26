import type { FeedIssue, IssueDetailResponse, SearchResult } from "@/lib/api/types";

type MockIssue = FeedIssue & Pick<IssueDetailResponse, "body" | "github_url" | "repo_url" | "state">;

export const mockIssues: MockIssue[] = [
  {
    node_id: "I_kwDOExample1",
    title: "Add dark mode support to dashboard",
    body_preview: "Users have requested a dark mode option for better visibility during nighttime usage...",
    body: `# Feature Request

## Description
Users have requested a dark mode option for better visibility during nighttime usage. This should include:

- Toggle in settings
- System preference detection
- Persistent preference storage

## Proposed Solution
Implement a theme context provider that manages light/dark mode state and applies CSS custom properties accordingly.

## Additional Context
Several users have reported eye strain when using the dashboard at night. This feature would improve accessibility and user comfort.`,
    labels: ["enhancement", "good first issue", "help wanted"],
    q_score: 0.85,
    repo_name: "acme/dashboard",
    primary_language: "TypeScript",
    github_created_at: "2025-12-15T10:30:00Z",
    github_url: "https://github.com/acme/dashboard/issues/42",
    repo_url: "https://github.com/acme/dashboard",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample2",
    title: "Fix memory leak in WebSocket connection handler",
    body_preview: "There's a memory leak occurring when WebSocket connections are dropped unexpectedly...",
    body: `# Bug Report

## Description
There's a memory leak occurring when WebSocket connections are dropped unexpectedly. The connection cleanup handler isn't properly disposing of event listeners.

## Steps to Reproduce
1. Open a WebSocket connection
2. Kill the connection from the server side
3. Repeat 100 times
4. Observe memory usage climbing

## Expected Behavior
Memory should be stable after connections are closed.

## Environment
- Node.js 20.x
- ws package 8.14.0`,
    labels: ["bug", "memory", "high priority"],
    q_score: 0.92,
    repo_name: "socketio/socket.io",
    primary_language: "JavaScript",
    github_created_at: "2025-11-28T14:22:00Z",
    github_url: "https://github.com/socketio/socket.io/issues/4521",
    repo_url: "https://github.com/socketio/socket.io",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample3",
    title: "Implement OAuth2 PKCE flow for mobile apps",
    body_preview: "Mobile applications need PKCE support for secure authentication without client secrets...",
    body: `# Feature Request

## Description
Mobile applications need PKCE (Proof Key for Code Exchange) support for secure authentication without exposing client secrets.

## Requirements
- Support code_verifier and code_challenge parameters
- SHA256 challenge method
- Backwards compatible with existing OAuth2 flow

## References
- RFC 7636: https://tools.ietf.org/html/rfc7636`,
    labels: ["enhancement", "security", "authentication"],
    q_score: 0.78,
    repo_name: "nextauthjs/next-auth",
    primary_language: "TypeScript",
    github_created_at: "2025-12-01T09:15:00Z",
    github_url: "https://github.com/nextauthjs/next-auth/issues/8234",
    repo_url: "https://github.com/nextauthjs/next-auth",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample4",
    title: "Add Python 3.12 support",
    body_preview: "The library should be tested and certified for Python 3.12 compatibility...",
    body: `# Feature Request

## Description
Python 3.12 has been released and we need to ensure compatibility with the latest version.

## Tasks
- [ ] Update CI matrix to include Python 3.12
- [ ] Fix any deprecation warnings
- [ ] Update documentation
- [ ] Release new version with py312 classifier`,
    labels: ["enhancement", "python", "good first issue"],
    q_score: 0.71,
    repo_name: "pandas-dev/pandas",
    primary_language: "Python",
    github_created_at: "2025-10-20T16:45:00Z",
    github_url: "https://github.com/pandas-dev/pandas/issues/55123",
    repo_url: "https://github.com/pandas-dev/pandas",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample5",
    title: "Improve error messages for invalid configuration",
    body_preview: "Current error messages when configuration is invalid are cryptic and unhelpful...",
    body: `# Enhancement

## Problem
Current error messages when configuration is invalid are cryptic and unhelpful. Users struggle to understand what's wrong.

## Example
Current: \`ConfigError: Invalid value at path\`
Better: \`ConfigError: Expected 'port' to be a number between 1-65535, got 'invalid'\`

## Acceptance Criteria
- All config validation errors include the field name
- Error messages suggest valid values or formats
- Link to documentation where applicable`,
    labels: ["enhancement", "dx", "documentation"],
    q_score: 0.65,
    repo_name: "vercel/next.js",
    primary_language: "TypeScript",
    github_created_at: "2025-12-10T11:30:00Z",
    github_url: "https://github.com/vercel/next.js/issues/58421",
    repo_url: "https://github.com/vercel/next.js",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample6",
    title: "Add support for custom serializers in cache layer",
    body_preview: "Allow users to provide custom serialization functions for complex data types...",
    body: `# Feature Request

## Description
Allow users to provide custom serialization functions for complex data types that aren't JSON-serializable by default.

## Use Case
We need to cache instances of custom classes with circular references. The current JSON serialization fails for these.

## Proposed API
\`\`\`typescript
const cache = createCache({
  serializer: {
    serialize: (value) => customSerialize(value),
    deserialize: (data) => customDeserialize(data),
  }
});
\`\`\``,
    labels: ["enhancement", "caching", "help wanted"],
    q_score: 0.73,
    repo_name: "redis/redis-om-node",
    primary_language: "TypeScript",
    github_created_at: "2025-11-15T08:20:00Z",
    github_url: "https://github.com/redis/redis-om-node/issues/342",
    repo_url: "https://github.com/redis/redis-om-node",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample7",
    title: "Fix race condition in concurrent database migrations",
    body_preview: "Running migrations concurrently from multiple instances causes table lock conflicts...",
    body: `# Bug Report

## Description
Running migrations concurrently from multiple instances causes table lock conflicts and partial migrations.

## Environment
- PostgreSQL 15
- Multiple Kubernetes pods starting simultaneously

## Expected Behavior
Migrations should use advisory locks to prevent concurrent execution.

## Workaround
Currently we're using init containers to run migrations before app pods start.`,
    labels: ["bug", "database", "kubernetes"],
    q_score: 0.88,
    repo_name: "prisma/prisma",
    primary_language: "TypeScript",
    github_created_at: "2025-12-05T13:10:00Z",
    github_url: "https://github.com/prisma/prisma/issues/21534",
    repo_url: "https://github.com/prisma/prisma",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample8",
    title: "Implement streaming responses for large datasets",
    body_preview: "Large API responses should support streaming to reduce memory usage and improve TTFB...",
    body: `# Feature Request

## Description
Large API responses should support streaming to reduce memory usage and improve Time To First Byte (TTFB).

## Current Behavior
The entire response is buffered in memory before sending.

## Proposed Behavior
Support \`Transfer-Encoding: chunked\` for responses over a configurable threshold.`,
    labels: ["enhancement", "performance", "api"],
    q_score: 0.81,
    repo_name: "fastify/fastify",
    primary_language: "JavaScript",
    github_created_at: "2025-11-22T15:45:00Z",
    github_url: "https://github.com/fastify/fastify/issues/5123",
    repo_url: "https://github.com/fastify/fastify",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample9",
    title: "Add Rust bindings for the core library",
    body_preview: "Create Rust FFI bindings to allow usage from Rust applications...",
    body: `# Feature Request

## Description
Create Rust FFI bindings to allow usage from Rust applications. This would expand the library's reach to the growing Rust ecosystem.

## Scope
- Core functionality only (no UI components)
- Safe wrapper around unsafe FFI calls
- Published to crates.io

## Prior Art
Similar libraries have Rust bindings: libgit2, sqlite, etc.`,
    labels: ["enhancement", "rust", "ffi", "good first issue"],
    q_score: 0.69,
    repo_name: "nickel-org/nickel.rs",
    primary_language: "Rust",
    github_created_at: "2025-12-08T10:00:00Z",
    github_url: "https://github.com/nickel-org/nickel.rs/issues/892",
    repo_url: "https://github.com/nickel-org/nickel.rs",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample10",
    title: "Fix SVG rendering issues on Safari",
    body_preview: "SVG elements with complex gradients don't render correctly on Safari browsers...",
    body: `# Bug Report

## Description
SVG elements with complex gradients don't render correctly on Safari browsers. The gradients appear blocky or missing entirely.

## Steps to Reproduce
1. Open the chart component on Safari 17+
2. Observe gradient fills on bar charts
3. Compare with Chrome/Firefox

## Screenshots
[Attached comparison screenshots]

## Browser
Safari 17.2 on macOS Sonoma`,
    labels: ["bug", "safari", "svg", "help wanted"],
    q_score: 0.76,
    repo_name: "recharts/recharts",
    primary_language: "TypeScript",
    github_created_at: "2025-12-12T09:30:00Z",
    github_url: "https://github.com/recharts/recharts/issues/4012",
    repo_url: "https://github.com/recharts/recharts",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample11",
    title: "Add internationalization (i18n) support",
    body_preview: "The application should support multiple languages and locales...",
    body: `# Feature Request

## Description
The application should support multiple languages and locales for global users.

## Requirements
- Language detection from browser settings
- RTL support for Arabic/Hebrew
- Date/number formatting per locale
- Translation management workflow

## Initial Languages
- English (default)
- Spanish
- French
- German
- Japanese`,
    labels: ["enhancement", "i18n", "accessibility"],
    q_score: 0.82,
    repo_name: "shadcn/ui",
    primary_language: "TypeScript",
    github_created_at: "2025-11-30T12:15:00Z",
    github_url: "https://github.com/shadcn/ui/issues/2341",
    repo_url: "https://github.com/shadcn/ui",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample12",
    title: "Optimize Docker image size",
    body_preview: "The production Docker image is currently 1.2GB and should be reduced...",
    body: `# Optimization

## Current State
Production Docker image: 1.2GB
Build time: ~8 minutes

## Target
Image size: <300MB
Build time: <3 minutes

## Proposed Changes
- Switch to Alpine base image
- Multi-stage build
- Prune dev dependencies
- Use .dockerignore`,
    labels: ["enhancement", "docker", "performance"],
    q_score: 0.74,
    repo_name: "docker/compose",
    primary_language: "Go",
    github_created_at: "2025-12-03T14:20:00Z",
    github_url: "https://github.com/docker/compose/issues/11234",
    repo_url: "https://github.com/docker/compose",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample13",
    title: "Add keyboard navigation to dropdown menus",
    body_preview: "Dropdown menus should be fully navigable using keyboard only...",
    body: `# Accessibility

## Description
Dropdown menus should be fully navigable using keyboard only for users who cannot use a mouse.

## Required Keyboard Shortcuts
- Enter/Space: Open dropdown, select item
- Escape: Close dropdown
- Arrow Up/Down: Navigate items
- Home/End: Jump to first/last item
- Type-ahead: Jump to matching item

## WCAG Reference
WCAG 2.1 Success Criterion 2.1.1 (Keyboard)`,
    labels: ["enhancement", "accessibility", "a11y"],
    q_score: 0.87,
    repo_name: "radix-ui/primitives",
    primary_language: "TypeScript",
    github_created_at: "2025-11-25T11:00:00Z",
    github_url: "https://github.com/radix-ui/primitives/issues/2567",
    repo_url: "https://github.com/radix-ui/primitives",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample14",
    title: "GraphQL subscriptions not reconnecting after network loss",
    body_preview: "WebSocket subscriptions don't automatically reconnect when network is restored...",
    body: `# Bug Report

## Description
WebSocket subscriptions don't automatically reconnect when network is restored after temporary loss.

## Steps to Reproduce
1. Start a subscription
2. Disable network (airplane mode)
3. Re-enable network
4. Subscription remains dead

## Expected
Automatic reconnection with exponential backoff.`,
    labels: ["bug", "graphql", "websocket"],
    q_score: 0.79,
    repo_name: "apollographql/apollo-client",
    primary_language: "TypeScript",
    github_created_at: "2025-12-07T16:30:00Z",
    github_url: "https://github.com/apollographql/apollo-client/issues/11892",
    repo_url: "https://github.com/apollographql/apollo-client",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
  {
    node_id: "I_kwDOExample15",
    title: "Add support for ARM64 builds",
    body_preview: "Pre-built binaries should include ARM64 variants for Apple Silicon and AWS Graviton...",
    body: `# Feature Request

## Description
Pre-built binaries should include ARM64 variants for Apple Silicon Macs and AWS Graviton instances.

## Current State
Only x86_64 binaries are provided, requiring compilation from source on ARM64.

## Impact
- Faster setup on Apple Silicon
- Cost savings on AWS Graviton
- Better CI/CD support`,
    labels: ["enhancement", "arm64", "build"],
    q_score: 0.68,
    repo_name: "evanw/esbuild",
    primary_language: "Go",
    github_created_at: "2025-11-18T13:45:00Z",
    github_url: "https://github.com/evanw/esbuild/issues/3421",
    repo_url: "https://github.com/evanw/esbuild",
    state: "open",
    similarity_score: null,
    why_this: null,
  },
];

export function getMockIssueByNodeId(nodeId: string): MockIssue | undefined {
  return mockIssues.find((issue) => issue.node_id === nodeId);
}

export function getMockIssueDetail(nodeId: string): IssueDetailResponse | undefined {
  const issue = getMockIssueByNodeId(nodeId);
  if (!issue) return undefined;
  
  return {
    node_id: issue.node_id,
    title: issue.title,
    body: issue.body,
    labels: issue.labels,
    q_score: issue.q_score,
    repo_name: issue.repo_name,
    repo_url: issue.repo_url,
    github_url: issue.github_url,
    primary_language: issue.primary_language,
    github_created_at: issue.github_created_at,
    state: issue.state,
  };
}

export function filterMockIssues(
  query?: string,
  filters?: { languages?: string[]; labels?: string[]; repos?: string[] }
): SearchResult[] {
  let results = [...mockIssues];

  if (query) {
    const q = query.toLowerCase();
    results = results.filter(
      (issue) =>
        issue.title.toLowerCase().includes(q) ||
        issue.body_preview.toLowerCase().includes(q) ||
        issue.repo_name.toLowerCase().includes(q)
    );
  }

  if (filters?.languages?.length) {
    results = results.filter((issue) =>
      filters.languages!.some(
        (lang) => issue.primary_language.toLowerCase() === lang.toLowerCase()
      )
    );
  }

  if (filters?.labels?.length) {
    results = results.filter((issue) =>
      filters.labels!.some((label) =>
        issue.labels.map((l) => l.toLowerCase()).includes(label.toLowerCase())
      )
    );
  }

  if (filters?.repos?.length) {
    results = results.filter((issue) =>
      filters.repos!.some(
        (repo) => issue.repo_name.toLowerCase() === repo.toLowerCase()
      )
    );
  }

  return results.map((issue) => ({
    node_id: issue.node_id,
    title: issue.title,
    body_preview: issue.body_preview,
    labels: issue.labels,
    q_score: issue.q_score,
    repo_name: issue.repo_name,
    primary_language: issue.primary_language,
    github_created_at: issue.github_created_at,
    rrf_score: Math.random() * 0.5 + 0.5,
  }));
}

export function getSimilarIssues(nodeId: string, limit: number) {
  const currentIssue = getMockIssueByNodeId(nodeId);
  if (!currentIssue) return [];

  return mockIssues
    .filter((issue) => issue.node_id !== nodeId)
    .filter(
      (issue) =>
        issue.primary_language === currentIssue.primary_language ||
        issue.labels.some((l) => currentIssue.labels.includes(l))
    )
    .slice(0, limit)
    .map((issue) => ({
      node_id: issue.node_id,
      title: issue.title,
      repo_name: issue.repo_name,
      similarity_score: Math.random() * 0.4 + 0.5,
    }));
}
