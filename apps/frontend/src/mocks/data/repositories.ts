import type { RepositoriesResponse } from "@/lib/api/types";

export const mockRepositories: RepositoriesResponse["repositories"] = [
  { name: "vercel/next.js", primary_language: "TypeScript", issue_count: 342 },
  { name: "facebook/react", primary_language: "JavaScript", issue_count: 287 },
  { name: "microsoft/typescript", primary_language: "TypeScript", issue_count: 456 },
  { name: "nodejs/node", primary_language: "JavaScript", issue_count: 523 },
  { name: "prisma/prisma", primary_language: "TypeScript", issue_count: 189 },
  { name: "tailwindlabs/tailwindcss", primary_language: "TypeScript", issue_count: 134 },
  { name: "vitejs/vite", primary_language: "TypeScript", issue_count: 167 },
  { name: "sveltejs/svelte", primary_language: "TypeScript", issue_count: 98 },
  { name: "vuejs/vue", primary_language: "TypeScript", issue_count: 112 },
  { name: "angular/angular", primary_language: "TypeScript", issue_count: 234 },
  { name: "django/django", primary_language: "Python", issue_count: 321 },
  { name: "pallets/flask", primary_language: "Python", issue_count: 87 },
  { name: "fastapi/fastapi", primary_language: "Python", issue_count: 156 },
  { name: "pandas-dev/pandas", primary_language: "Python", issue_count: 412 },
  { name: "numpy/numpy", primary_language: "Python", issue_count: 289 },
  { name: "rust-lang/rust", primary_language: "Rust", issue_count: 567 },
  { name: "tokio-rs/tokio", primary_language: "Rust", issue_count: 143 },
  { name: "denoland/deno", primary_language: "Rust", issue_count: 198 },
  { name: "golang/go", primary_language: "Go", issue_count: 378 },
  { name: "docker/compose", primary_language: "Go", issue_count: 156 },
  { name: "kubernetes/kubernetes", primary_language: "Go", issue_count: 789 },
  { name: "rails/rails", primary_language: "Ruby", issue_count: 234 },
  { name: "jekyll/jekyll", primary_language: "Ruby", issue_count: 67 },
  { name: "spring-projects/spring-boot", primary_language: "Java", issue_count: 298 },
  { name: "elastic/elasticsearch", primary_language: "Java", issue_count: 345 },
];

export function filterRepositories(params: {
  q?: string;
  language?: string;
  limit?: number;
}): RepositoriesResponse["repositories"] {
  let results = [...mockRepositories];

  if (params.q) {
    const query = params.q.toLowerCase();
    results = results.filter((repo) => repo.name.toLowerCase().includes(query));
  }

  if (params.language) {
    const lang = params.language.toLowerCase();
    results = results.filter(
      (repo) => repo.primary_language.toLowerCase() === lang
    );
  }

  if (params.limit) {
    results = results.slice(0, params.limit);
  }

  return results;
}
