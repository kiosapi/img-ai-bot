"use client";

import { GenJobProvider } from "@/lib/gen-job";

export function Providers({ children }: { children: React.ReactNode }) {
  return <GenJobProvider>{children}</GenJobProvider>;
}
