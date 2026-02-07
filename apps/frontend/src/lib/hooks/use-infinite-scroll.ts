import { useEffect, useRef } from "react";

export function useInfiniteScroll(opts: {
  hasNextPage: boolean | undefined;
  isFetchingNextPage: boolean;
  fetchNextPage: () => void;
}) {
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && opts.hasNextPage && !opts.isFetchingNextPage) {
          opts.fetchNextPage();
        }
      },
      { rootMargin: "200px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [opts.hasNextPage, opts.isFetchingNextPage, opts.fetchNextPage]);

  return sentinelRef;
}
