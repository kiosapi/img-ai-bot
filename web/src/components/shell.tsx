"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { LayoutGrid, Users, Radio, Settings, Moon, Sun, LogOut, Sparkles } from "lucide-react";
import { cn, api } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutGrid },
  { href: "/users", label: "User", icon: Users },
  { href: "/broadcast", label: "Broadcast", icon: Radio },
  { href: "/settings", label: "Setting", icon: Settings },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  async function logout() {
    await api("/api/logout", { method: "POST" }).catch(() => {});
    router.push("/login");
  }

  return (
    <div className="min-h-screen md:flex">
      {/* Sidebar (desktop) */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 border-r bg-card px-4 py-6">
        <div className="flex items-center gap-2 px-2 mb-8">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="h-5 w-5" />
          </div>
          <span className="font-bold text-lg">Image Bot</span>
        </div>
        <nav className="flex flex-col gap-1 flex-1">
          {nav.map((n) => {
            const active = path === n.href;
            return (
              <Link key={n.href} href={n.href}
                className={cn("flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                  active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
                <n.icon className="h-5 w-5" />{n.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex flex-col gap-1">
          {mounted && (
            <Button variant="ghost" className="justify-start" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              {theme === "dark" ? "Light Mode" : "Dark Mode"}
            </Button>
          )}
          <Button variant="ghost" className="justify-start text-destructive" onClick={logout}>
            <LogOut className="h-5 w-5" />Keluar
          </Button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 md:ml-64 pb-24 md:pb-8">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-card/80 backdrop-blur px-5 py-4 md:hidden">
          <span className="font-bold text-lg">Image Bot</span>
          {mounted && (
            <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")} className="p-1">
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
          )}
        </header>
        <div className="mx-auto max-w-4xl p-5">{children}</div>
      </main>

      {/* Bottom tab bar (mobile) */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 flex justify-around border-t bg-card/90 backdrop-blur pb-[env(safe-area-inset-bottom)]">
        {nav.map((n) => {
          const active = path === n.href;
          return (
            <Link key={n.href} href={n.href}
              className={cn("flex flex-col items-center gap-1 py-2.5 px-4 text-[11px] font-medium",
                active ? "text-primary" : "text-muted-foreground")}>
              <n.icon className="h-6 w-6" />{n.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
