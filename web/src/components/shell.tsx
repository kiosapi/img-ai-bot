"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { LayoutGrid, Users, Radio, Settings, Moon, Sun, LogOut, Sparkles, BarChart3, AlertTriangle, Crown, CreditCard, Receipt, Menu, X, Wallet, ArrowDownToLine, Gift, Bot, ShieldCheck, ScrollText, Server, HeartPulse, FileText, Palette, Command, Route, Link2, Zap, Bell, ShieldAlert, DollarSign, CalendarRange, HardDrive } from "lucide-react";
import { cn, api } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useLang, FlagID, FlagEN } from "@/lib/i18n";

const groups = [
  {
    titleKey: "nav.general" as const,
    items: [
      { href: "/", labelKey: "nav.dashboard", icon: LayoutGrid },
      { href: "/analytics", labelKey: "nav.analytics", icon: BarChart3 },
      { href: "/system", labelKey: "nav.system", icon: Server },
      { href: "/health", labelKey: "nav.health", icon: HeartPulse },
      { href: "/failover", labelKey: "nav.failover", icon: Route },
      { href: "/cost", labelKey: "nav.cost", icon: DollarSign },
      { href: "/alerts", labelKey: "nav.alerts", icon: Bell },
      { href: "/moderation", labelKey: "nav.moderation", icon: ShieldAlert },
      { href: "/users", labelKey: "nav.users", icon: Users },
      { href: "/broadcast", labelKey: "nav.broadcast", icon: Radio },
      { href: "/broadcast-sched", labelKey: "nav.broadcast_sched", icon: CalendarRange },
      { href: "/backup", labelKey: "nav.backup", icon: HardDrive },
      { href: "/referral", labelKey: "nav.referral", icon: Gift },
      { href: "/models", labelKey: "nav.models", icon: Bot },
      { href: "/styles-manage", labelKey: "nav.styles_manage", icon: Palette },
      { href: "/texts", labelKey: "nav.texts", icon: FileText },
      { href: "/commands", labelKey: "nav.commands", icon: Command },
      { href: "/errors", labelKey: "nav.errors", icon: AlertTriangle },
      { href: "/logs", labelKey: "nav.logs", icon: ScrollText },
      { href: "/settings", labelKey: "nav.settings", icon: Settings },
      { href: "/audit", labelKey: "nav.audit", icon: ShieldCheck },
    ],
  },
  {
    titleKey: "nav.premium" as const,
    items: [
      { href: "/orders", labelKey: "nav.orders", icon: Receipt },
      { href: "/plans", labelKey: "nav.plans", icon: Crown },
      { href: "/payments", labelKey: "nav.payments", icon: CreditCard },
    ],
  },
  {
    titleKey: "nav.balance" as const,
    items: [
      { href: "/deposits", labelKey: "nav.deposits", icon: ArrowDownToLine },
      { href: "/balance-settings", labelKey: "nav.balance_settings", icon: Wallet },
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
  const { lang, setLang, t } = useLang();
  useEffect(() => setMounted(true), []);
  useEffect(() => { setOpen(false); }, [path]);
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
        <div key={g.titleKey}>
          <div className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{t(g.titleKey)}</div>
          <div className="flex flex-col gap-1">
            {g.items.map((n) => {
              const active = isActive(path, n.href);
              return (
                <Link key={n.href} href={n.href} onClick={onNavigate}
                  className={cn("flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                    active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
                  <n.icon className="h-5 w-5" />{t(n.labelKey)}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );

  const LangToggle = () => (
    <div className="flex items-center gap-2 rounded-md border bg-muted/50 p-1">
      <button
        onClick={() => setLang("id")}
        className={cn("flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors", lang === "id" ? "bg-card shadow border text-foreground" : "text-muted-foreground hover:text-foreground")}>
        <FlagID className="h-3 w-[18px] rounded-[2px] overflow-hidden shrink-0" /> ID
      </button>
      <button
        onClick={() => setLang("en")}
        className={cn("flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors", lang === "en" ? "bg-card shadow border text-foreground" : "text-muted-foreground hover:text-foreground")}>
        <FlagEN className="h-3 w-[18px] rounded-[2px] overflow-hidden shrink-0" /> EN
      </button>
    </div>
  );

  const ThemeLogout = () => (
    <div className="flex flex-col gap-2 pt-4">
      <LangToggle />
      {mounted && (
        <Button variant="ghost" className="justify-start" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
          {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          {theme === "dark" ? t("nav.light") : t("nav.dark")}
        </Button>
      )}
      <Button variant="ghost" className="justify-start text-destructive" onClick={logout}>
        <LogOut className="h-5 w-5" />{t("nav.logout")}
      </Button>
    </div>
  );

  return (
    <div className="min-h-screen md:flex">
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

      <main className="flex-1 md:ml-64 pb-8">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-card/80 backdrop-blur px-4 py-3 md:hidden">
          <button onClick={() => setOpen(true)} className="rounded-md p-1.5 hover:bg-muted" aria-label="Open menu">
            <Menu className="h-6 w-6" />
          </button>
          <span className="font-bold text-lg">Image Bot</span>
          <div className="flex items-center gap-2">
            <div className="scale-90">
              <LangToggle />
            </div>
            {mounted ? (
              <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")} className="rounded-md p-1.5 hover:bg-muted" aria-label="Toggle theme">
                {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>
            ) : <span className="w-8" />}
          </div>
        </header>
        <div className="mx-auto max-w-4xl p-5">{children}</div>
      </main>
    </div>
  );
}
