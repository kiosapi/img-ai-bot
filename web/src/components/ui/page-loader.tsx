"use client";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md bg-muted",
        "after:absolute after:inset-0 after:-translate-x-full after:animate-[shimmer_1.4s_infinite]",
        "after:bg-gradient-to-r after:from-transparent after:via-foreground/10 after:to-transparent",
        className
      )}
    />
  );
}

/** Modern full-page / section loader for admin */
export function PageLoader({
  label,
  rows = 4,
  cards = 0,
}: {
  label?: string;
  rows?: number;
  cards?: number;
}) {
  return (
    <div className="flex w-full flex-col gap-4 py-2" role="status" aria-busy="true" aria-label={label || "Loading"}>
      <div className="flex items-center gap-3">
        <div className="relative h-8 w-8 shrink-0">
          <div className="absolute inset-0 rounded-full border-2 border-primary/20" />
          <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-primary" />
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-3.5 w-36" />
          <Skeleton className="h-2.5 w-52 max-w-full" />
        </div>
      </div>
      {cards > 0 && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: cards }).map((_, i) => (
            <div key={i} className="rounded-lg border bg-card p-4">
              <Skeleton className="mb-3 h-2.5 w-16" />
              <Skeleton className="h-7 w-20" />
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-col gap-0 overflow-hidden rounded-lg border bg-card">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 border-b px-4 py-3 last:border-0">
            <Skeleton className="h-9 w-9 shrink-0 rounded-full" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-3 w-40 max-w-full" />
              <Skeleton className="h-2.5 w-28 max-w-[70%]" />
            </div>
            <Skeleton className="h-8 w-16 shrink-0 rounded-md" />
          </div>
        ))}
      </div>
      {label ? <p className="text-center text-xs text-muted-foreground">{label}</p> : null}
    </div>
  );
}
