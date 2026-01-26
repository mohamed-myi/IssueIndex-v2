import type { TaxonomyLanguagesResponse, TaxonomyStackAreasResponse } from "@/lib/api/types";

export const mockLanguages: TaxonomyLanguagesResponse = {
  languages: [
    "TypeScript",
    "JavaScript",
    "Python",
    "Rust",
    "Go",
    "Java",
    "Ruby",
    "C++",
    "C#",
    "PHP",
    "Swift",
    "Kotlin",
    "Scala",
    "Elixir",
    "Haskell",
    "Clojure",
    "R",
    "Julia",
    "Dart",
    "Lua",
    "Perl",
    "Shell",
    "PowerShell",
    "Objective-C",
    "MATLAB",
    "Groovy",
    "F#",
    "OCaml",
    "Erlang",
    "Zig",
    "Nim",
    "Crystal",
  ],
};

export const mockStackAreas: TaxonomyStackAreasResponse = {
  stack_areas: [
    {
      id: "frontend",
      label: "Frontend Development",
      description: "Building user interfaces and client-side applications",
    },
    {
      id: "backend",
      label: "Backend Development",
      description: "Server-side logic, APIs, and data processing",
    },
    {
      id: "fullstack",
      label: "Full Stack Development",
      description: "End-to-end web application development",
    },
    {
      id: "mobile",
      label: "Mobile Development",
      description: "iOS, Android, and cross-platform mobile apps",
    },
    {
      id: "devops",
      label: "DevOps & Infrastructure",
      description: "CI/CD, cloud infrastructure, and deployment automation",
    },
    {
      id: "data",
      label: "Data Engineering",
      description: "Data pipelines, ETL, and data infrastructure",
    },
    {
      id: "ml",
      label: "Machine Learning",
      description: "ML models, training pipelines, and AI systems",
    },
    {
      id: "security",
      label: "Security",
      description: "Application security, cryptography, and vulnerability research",
    },
    {
      id: "systems",
      label: "Systems Programming",
      description: "Operating systems, compilers, and low-level development",
    },
    {
      id: "database",
      label: "Database Development",
      description: "Database engines, query optimization, and storage systems",
    },
    {
      id: "blockchain",
      label: "Blockchain & Web3",
      description: "Smart contracts, DeFi, and decentralized applications",
    },
    {
      id: "gamedev",
      label: "Game Development",
      description: "Game engines, graphics, and interactive entertainment",
    },
  ],
};
