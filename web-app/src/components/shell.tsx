"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Sparkles, History, Palette, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

const NAV = [
  { href: "/app/", icon: Home, key: "nav.home" as const },
  { href: "/app/generate/", icon: Sparkles, key: "nav.generate" as const },
  { href: "/app/history/", icon: History, key: "nav.history" as const },
  { href: "/app/styles/", icon: Palette, key: "nav.styles" as const },
  { href: "/app/settings/", icon: Settings, key: "nav.settings" as const },
];

export function AppShell({
  children,
  lang,
}: {
  children: React.ReactNode;
  lang: Lang;
}) {
  const pathname = usePathname() || "/";

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-lg flex-col px-4 pb-24 pt-5 sm:max-w-2xl">
      <header className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Sparkles className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold tracking-tight">{t("app.name", lang)}</span>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <nav className="fixed bottom-0 left-0 right-0 border-t border-border bg-card/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-lg items-stretch justify-between px-2 py-2 sm:max-w-2xl">
          {NAV.map((item) => {
            const active =
              pathname === item.href ||
              (item.href !== "/app/" && pathname.startsWith(item.href.replace(/\/$/, "")));
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex min-h-[44px] min-w-[44px] flex-1 flex-col items-center justify-center gap-0.5 rounded-lg text-[10px] font-medium sm:text-xs",
                  active ? "text-primary" : "text-muted-foreground"
                )}
              >
                <Icon className="h-5 w-5" />
                <span>{t(item.key, lang)}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
