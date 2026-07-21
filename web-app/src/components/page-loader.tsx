"use client";

import { cn } from "@/lib/utils";

/** Modern skeleton blocks — Lucide-free, zero emoji */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg bg-muted/80",
        "after:absolute after:inset-0 after:-translate-x-full after:animate-[shimmer_1.4s_infinite]",
        "after:bg-gradient-to-r after:from-transparent after:via-white/10 after:to-transparent",
        className
      )}
    />
  );
}

export function PageLoader({
  label = "Memuat…",
  cards = 4,
}: {
  label?: string;
  cards?: number;
}) {
  return (
    <div className="flex flex-col gap-4 py-2" role="status" aria-busy="true" aria-label={label}>
      <div className="flex items-center gap-3">
        <div className="relative h-8 w-8">
          <div className="absolute inset-0 rounded-full border-2 border-primary/20" />
          <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-primary" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-2.5 w-40" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {Array.from({ length: cards }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border bg-card p-4">
            <Skeleton className="mb-3 h-2.5 w-16" />
            <Skeleton className="h-6 w-24" />
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-border bg-card p-4">
        <Skeleton className="mb-2 h-3 w-full" />
        <Skeleton className="mb-2 h-3 w-5/6 max-w-[90%]" />
        <Skeleton className="h-3 w-2/3 max-w-[70%]" />
      </div>
    </div>
  );
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2" role="status" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border bg-card p-3">
          <div className="mb-2 flex justify-between">
            <Skeleton className="h-2.5 w-14" />
            <Skeleton className="h-2.5 w-20" />
          </div>
          <Skeleton className="mb-1.5 h-3 w-full" />
          <Skeleton className="h-3 w-3/4 max-w-[80%]" />
        </div>
      ))}
    </div>
  );
}
