"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

/** Top route progress bar — modern, not fake full-page spinner */
export function RouteProgress() {
  const path = usePathname();
  const [on, setOn] = useState(false);

  useEffect(() => {
    setOn(true);
    const t = window.setTimeout(() => setOn(false), 420);
    return () => window.clearTimeout(t);
  }, [path]);

  if (!on) return null;

  return (
    <div className="pointer-events-none fixed left-0 right-0 top-0 z-[100] h-0.5 overflow-hidden bg-primary/10">
      <div
        className="h-full w-1/3 rounded-full bg-primary"
        style={{ animation: "routeBar 0.42s ease-out forwards" }}
      />
    </div>
  );
}
