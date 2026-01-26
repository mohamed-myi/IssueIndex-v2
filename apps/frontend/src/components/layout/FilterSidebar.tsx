"use client";

import { ChevronDown, ChevronRight, SlidersHorizontal, X } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";

export type FilterState = {
  language: string | null;
  label: string | null;
  repo: string | null;
};

type FilterSidebarProps = {
  isVisible: boolean;
  languages: string[];
  labels: string[];
  repos: string[];
  value: FilterState;
  onChange: (next: FilterState) => void;
};

export function FilterSidebar({ isVisible, languages, labels, repos, value, onChange }: FilterSidebarProps) {
  const hasActiveFilters = Boolean(value.language || value.label || value.repo);
  const [showAllLanguages, setShowAllLanguages] = useState(false);
  const [showAllLabels, setShowAllLabels] = useState(false);
  const [showAllRepos, setShowAllRepos] = useState(false);

  const visibleLanguages = useMemo(() => (showAllLanguages ? languages : languages.slice(0, 8)), [showAllLanguages, languages]);
  const visibleLabels = useMemo(() => (showAllLabels ? labels : labels.slice(0, 8)), [showAllLabels, labels]);
  const visibleRepos = useMemo(() => (showAllRepos ? repos : repos.slice(0, 8)), [showAllRepos, repos]);

  if (!isVisible) {
    return null;
  }

  function clear() {
    onChange({ language: null, label: null, repo: null });
  }

  return (
    <aside
      className="fixed bottom-0 left-0 top-[var(--topnav-height)] w-[var(--sidebar-width)] flex-shrink-0 overflow-y-auto pl-6 pr-4 pt-6 transition-all duration-300"
      style={{ backgroundColor: "var(--sidebar)", borderRight: "1px solid var(--sidebar-border)" }}
    >
      <div className="space-y-6 pb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <SlidersHorizontal className="h-4 w-4" style={{ color: "rgba(255, 255, 255, 0.40)" }} />
            <h2 className="text-[16px] font-bold tracking-tight" style={{ color: "rgba(255, 255, 255, 0.90)" }}>
              Filters
            </h2>
          </div>
          {hasActiveFilters ? (
            <button
              type="button"
              onClick={clear}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-medium transition-colors hover:bg-white/5"
              style={{ color: "rgba(255, 255, 255, 0.45)" }}
            >
              <X className="h-3 w-3" />
              Clear
            </button>
          ) : null}
        </div>

        <div className="h-px" style={{ backgroundColor: "rgba(255, 255, 255, 0.06)" }} />

        <FilterSection
          title="Language"
          items={visibleLanguages}
          selected={value.language}
          onSelect={(language) => onChange({ ...value, language })}
          canToggleMore={languages.length > visibleLanguages.length}
          expanded={showAllLanguages}
          onToggleExpanded={() => setShowAllLanguages((v) => !v)}
          moreCount={Math.max(0, languages.length - visibleLanguages.length)}
        />

        <FilterSection
          title="Label"
          items={visibleLabels}
          selected={value.label}
          onSelect={(label) => onChange({ ...value, label })}
          canToggleMore={labels.length > visibleLabels.length}
          expanded={showAllLabels}
          onToggleExpanded={() => setShowAllLabels((v) => !v)}
          moreCount={Math.max(0, labels.length - visibleLabels.length)}
        />

        <FilterSection
          title="Repository"
          items={visibleRepos}
          selected={value.repo}
          onSelect={(repo) => onChange({ ...value, repo })}
          canToggleMore={repos.length > visibleRepos.length}
          expanded={showAllRepos}
          onToggleExpanded={() => setShowAllRepos((v) => !v)}
          moreCount={Math.max(0, repos.length - visibleRepos.length)}
          truncate
        />
      </div>
    </aside>
  );
}

function FilterSection(props: {
  title: string;
  items: string[];
  selected: string | null;
  onSelect: (value: string | null) => void;
  canToggleMore: boolean;
  expanded: boolean;
  onToggleExpanded: () => void;
  moreCount: number;
  truncate?: boolean;
}) {
  return (
    <div>
      <label
        className="mb-2 block px-1 text-[10px] font-semibold uppercase tracking-widest"
        style={{ color: "#71717a", letterSpacing: "0.1em" }}
      >
        {props.title}
      </label>

      <div className="space-y-0.5">
        <button
          type="button"
          onClick={() => props.onSelect(null)}
          className={cn(
            "relative w-full rounded-xl px-3 py-1.5 text-left text-[12px] transition-all duration-150",
            props.truncate ? "truncate" : "",
          )}
          style={{
            backgroundColor: props.selected === null ? "rgba(138, 92, 255, 0.12)" : "transparent",
            color: props.selected === null ? "#E6E9F2" : "#8A90B2",
            fontWeight: props.selected === null ? 600 : 400,
            borderLeft: props.selected === null ? "2px solid rgba(138, 92, 255, 0.6)" : "2px solid transparent",
          }}
        >
          All
        </button>

        {props.items.map((item) => {
          const selected = props.selected === item;
          return (
            <button
              key={item}
              type="button"
              onClick={() => props.onSelect(item)}
              className={cn(
                "relative w-full rounded-xl px-3 py-1.5 text-left text-[12px] transition-all duration-150",
                props.truncate ? "truncate" : "",
              )}
              style={{
                backgroundColor: selected ? "rgba(138, 92, 255, 0.12)" : "transparent",
                color: selected ? "#E6E9F2" : "#8A90B2",
                fontWeight: selected ? 600 : 400,
                borderLeft: selected ? "2px solid rgba(138, 92, 255, 0.6)" : "2px solid transparent",
              }}
            >
              {item}
            </button>
          );
        })}

        {props.canToggleMore ? (
          <button
            type="button"
            onClick={props.onToggleExpanded}
            className="flex w-full items-center gap-1.5 rounded-xl px-3 py-1.5 text-left text-[11px] transition-all duration-150"
            style={{ color: "rgba(255, 255, 255, 0.45)" }}
          >
            {props.expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            {props.expanded ? "Show less" : `Show ${props.moreCount} more`}
          </button>
        ) : null}
      </div>
    </div>
  );
}

