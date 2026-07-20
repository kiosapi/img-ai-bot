"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { Search, Ban, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Badge } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";

const rupiah = (n: number) => "Rp" + Number(n || 0).toLocaleString("id-ID");

export default function UsersPage() {
  const { t, lang } = useLang();
  const [users, setUsers] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [totalCount, setTotalCount] = useState<number | null>(null);
  const firstLoad = useRef(true);

  useEffect(() => {
    const delay = firstLoad.current ? 0 : 350;
    const tmr = setTimeout(async () => {
      try {
        const data = await api(`/api/users?q=${encodeURIComponent(q)}`);
        setUsers(data);
        // diagnostic: fetch total via dashboard stats
        if (!q) {
          try {
            const stats = await api(`/api/stats`);
            setTotalCount(stats.total_users ?? data.length);
          } catch {
            setTotalCount(data.length);
          }
        }
      } catch {
        toast.error(lang === "id" ? "Gagal memuat user" : "Failed to load users");
      } finally {
        setInitialLoading(false);
        firstLoad.current = false;
      }
    }, delay);
    return () => clearTimeout(tmr);
  }, [q, lang]);

  async function toggleBan(u: any) {
    try {
      await api("/api/users/ban", { method: "POST", body: JSON.stringify({ user_id: u.user_id, banned: !u.is_banned }) });
      toast.success(u.is_banned ? (lang === "id" ? "User di-unban" : "User unbanned") : (lang === "id" ? "User dibanned" : "User banned"));
      setUsers((prev) => prev.map((x) => x.user_id === u.user_id ? { ...x, is_banned: !x.is_banned } : x));
    } catch { toast.error("Gagal"); }
  }

  return (
    <div className="flex flex-col gap-4 md:gap-5 p-1">
      <div>
        <h1 className="text-xl md:text-2xl font-bold tracking-tight">{t("users.title")}</h1>
        <p className="text-xs md:text-sm text-muted-foreground">{t("users.count", { n: users.length })}{totalCount !== null && totalCount !== users.length ? ` — total DB ${totalCount}` : ""}</p>
      </div>
      {totalCount === 1 && (
        <div className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{t("users.hint")}</span>
        </div>
      )}
      <div className="relative max-w-full">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-10" placeholder={t("users.search_ph")} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Card>
        <CardContent className="pt-0 px-0">
          {initialLoading ? (
            <div className="flex flex-col">{[0,1,2,3].map((i) => (<div key={i} className="flex items-center gap-3 border-b px-4 md:px-5 py-3 last:border-0"><div className="h-10 w-10 shrink-0 animate-pulse rounded-full bg-muted" /><div className="flex-1 space-y-2"><div className="h-3.5 w-32 animate-pulse rounded bg-muted" /><div className="h-3 w-24 animate-pulse rounded bg-muted" /></div></div>))}</div>
          ) : users.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">{t("users.empty")}</div>
          ) : users.map((u) => (
            <div key={u.user_id} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 border-b px-4 md:px-5 py-3 last:border-0">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-sm font-bold text-white">{(u.username || u.first_name || "U")[0].toUpperCase()}</div>
                <div className="min-w-0 flex-1">
                  <Link href={`/users/${u.user_id}`} className="block hover:opacity-70 transition-opacity">
                    <div className="truncate text-sm font-semibold">{u.username ? "@" + u.username : (u.first_name || "User")}{u.is_banned && <Badge variant="destructive" className="ml-2">{t("users.banned")}</Badge>}</div>
                    <div className="text-xs text-muted-foreground break-all">ID {u.user_id} — <Badge variant="default">{t("users.images", { n: u.gen_count })}</Badge> — <Badge variant="muted">{rupiah(u.balance)}</Badge> {u.last_seen ? `— last ${new Date(u.last_seen).toLocaleDateString()}` : ""}</div>
                  </Link>
                </div>
              </div>
              <div className="flex gap-2 shrink-0 self-end sm:self-auto">
                {u.is_banned ? <Button size="sm" variant="success" onClick={() => toggleBan(u)}><CheckCircle2 className="h-4 w-4 mr-1" />{t("users.unban")}</Button> : <Button size="sm" variant="destructive" onClick={() => toggleBan(u)}><Ban className="h-4 w-4 mr-1" />{t("users.ban")}</Button>}
                <Link href={`/users/${u.user_id}`}><Button size="sm" variant="outline">{t("users.detail")}</Button></Link>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
      <div className="text-[11px] text-muted-foreground">{t("users.hint")}</div>
    </div>
  );
}
