"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { LayoutGrid, Users, Radio, Settings, Moon, Sun, LogOut, Sparkles, BarChart3, AlertTriangle, Crown, CreditCard, Receipt, Menu, X } from "lucide-react";
import { cn, api } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const groups = [
  {
    title: "Umum",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutGrid },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/users", label: "User", icon: Users },
      { href: "/broadcast", label: "Broadcast", icon: Radio },
      { href: "/errors", label: "Error", icon: AlertTriangle },
      { href: "/settings", label: "Setting", icon: Settings },
    ],
  },
  {
    title: "Premium",
    items: [
      { href: "/orders", label: "Pesanan", icon: Receipt },
      { href: "/plans", label: "Paket", icon: Crown },
      { href: "/payments", label: "Pembayaran", icon: CreditCard },
    ],
  },
];
const isActive = (path: string, href: string) => (href === "/" ? path === "/" : path.startsWith(href));

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => setMounted(true), []);
  // Close the drawer whenever the route changes.
  useEffect(() => { setOpen(false); }, [path]);
  // Lock body scroll while the drawer is open.
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  async function logout() {
    await api("/api/logout", { method: "POST" }).catch(() => {});
    router.push("/login");
  }

  const NavLinks = ({ onNavigate }: { onNavigate?: () => void }) => (
    <nav className="flex flex-col gap-4">
      {groups.map((g) => (
        <div key={g.title}>
          <div className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{g.title}</div>
          <div className="flex flex-col gap-1">
            {g.items.map((n) => {
              const active = isActive(path, n.href);
              return (
                <Link key={n.href} href={n.href} onClick={onNavigate}
                  className={cn("flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                    active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
                  <n.icon className="h-5 w-5" />{n.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );

  const ThemeLogout = () => (
    <div className="flex flex-col gap-1 pt-4">
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
  );

  return (
    <div className="min-h-screen md:flex">
      {/* Sidebar (desktop) */}
      <aside className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 border-r bg-card px-4 py-6 overflow-y-auto">
        <div className="flex items-center gap-2 px-2 mb-8">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="h-5 w-5" />
          </div>
          <span className="font-bold text-lg">Image Bot</span>
        </div>
        <div className="flex-1"><NavLinks /></div>
        <ThemeLogout />
      </aside>

      {/* Mobile drawer */}
      <div className={cn("md:hidden fixed inset-0 z-50 transition-opacity duration-200", open ? "opacity-100" : "pointer-events-none opacity-0")}>
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
        <aside className={cn("absolute inset-y-0 left-0 w-72 max-w-[80%] flex flex-col border-r bg-card px-4 py-6 overflow-y-auto shadow-2xl transition-transform duration-200", open ? "translate-x-0" : "-translate-x-full")}>
          <div className="flex items-center justify-between px-2 mb-8">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Sparkles className="h-5 w-5" />
              </div>
              <span className="font-bold text-lg">Image Bot</span>
            </div>
            <button onClick={() => setOpen(false)} className="rounded-md p-1 text-muted-foreground hover:bg-muted"><X className="h-5 w-5" /></button>
          </div>
          <div className="flex-1"><NavLinks onNavigate={() => setOpen(false)} /></div>
          <ThemeLogout />
        </aside>
      </div>

      {/* Main */}
      <main className="flex-1 md:ml-64 pb-8">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-card/80 backdrop-blur px-4 py-3 md:hidden">
          <button onClick={() => setOpen(true)} className="rounded-md p-1.5 hover:bg-muted" aria-label="Buka menu">
            <Menu className="h-6 w-6" />
          </button>
          <span className="font-bold text-lg">Image Bot</span>
          {mounted ? (
            <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")} className="rounded-md p-1.5 hover:bg-muted" aria-label="Ganti tema">
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
          ) : <span className="w-8" />}
        </header>
        <div className="mx-auto max-w-4xl p-5">{children}</div>
      </main>
    </div>
  );
}
