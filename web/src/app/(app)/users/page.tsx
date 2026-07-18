"use client";
import { useEffect, useState, useRef } from "react";
import { Search, Ban, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Badge } from "@/components/ui/controls";

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);
  const firstLoad = useRef(true);

  useEffect(() => {
    // Single debounced effect. Runs immediately on mount (q="") and on every
    // query change. No second effect => no double fetch => no flicker.
    const delay = firstLoad.current ? 0 : 350;
    const t = setTimeout(async () => {
      try {
        const data = await api(`/api/users?q=${encodeURIComponent(q)}`);
        setUsers(data);
      } catch {
        toast.error("Gagal memuat user");
      } finally {
        setInitialLoading(false);
        firstLoad.current = false;
      }
    }, delay);
    return () => clearTimeout(t);
  }, [q]);

  async function toggleBan(u: any) {
    try {
      await api("/api/users/ban", { method: "POST", body: JSON.stringify({ user_id: u.user_id, banned: !u.is_banned }) });
      toast.success(u.is_banned ? "User di-unban" : "User dibanned");
      setUsers((prev) => prev.map((x) => x.user_id === u.user_id ? { ...x, is_banned: !x.is_banned } : x));
    } catch { toast.error("Gagal"); }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Kelola User</h1>
        <p className="text-sm text-muted-foreground">{users.length} user ditampilkan</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-10" placeholder="Cari username / ID / nama..." value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      <Card>
        <CardContent className="pt-0 px-0">
          {initialLoading ? (
            <div className="flex flex-col">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="flex items-center gap-3 border-b px-5 py-3 last:border-0">
                  <div className="h-10 w-10 shrink-0 animate-pulse rounded-full bg-muted" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3.5 w-32 animate-pulse rounded bg-muted" />
                    <div className="h-3 w-24 animate-pulse rounded bg-muted" />
                  </div>
                </div>
              ))}
            </div>
          ) : users.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">Tidak ada user</div>
          ) : users.map((u) => (
            <div key={u.user_id} className="flex items-center gap-3 border-b px-5 py-3 last:border-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-sm font-bold text-white">
                {(u.username || u.first_name || "U")[0].toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">
                  {u.username ? "@" + u.username : (u.first_name || "User")}
                  {u.is_banned && <Badge variant="destructive" className="ml-2">banned</Badge>}
                </div>
                <div className="text-xs text-muted-foreground">ID {u.user_id} · <Badge variant="default">{u.gen_count} gambar</Badge></div>
              </div>
              {u.is_banned
                ? <Button size="sm" variant="success" onClick={() => toggleBan(u)}><CheckCircle2 className="h-4 w-4" />Unban</Button>
                : <Button size="sm" variant="destructive" onClick={() => toggleBan(u)}><Ban className="h-4 w-4" />Ban</Button>}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
