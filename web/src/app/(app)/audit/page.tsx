"use client";
import { useEffect, useState } from "react";
import { ShieldCheck, RefreshCw } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";

export default function AuditPage() {
  const { t, lang } = useLang();
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const d = await api("/api/audit/logs?limit=200");
      setLogs(d.logs || []);
    } catch { setLogs([]); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  const actionBadge = (a: string) => {
    if (a.includes("login")) return <Badge variant="outline">{a}</Badge>;
    if (a.includes("ban") || a.includes("reject")) return <Badge variant="destructive">{a}</Badge>;
    if (a.includes("approve") || a.includes("balance")) return <Badge className="bg-emerald-500 text-white">{a}</Badge>;
    if (a.includes("broadcast")) return <Badge className="bg-amber-500 text-black">{a}</Badge>;
    return <Badge variant="muted">{a}</Badge>;
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><ShieldCheck className="h-6 w-6" />Audit Log</h1><p className="text-sm text-muted-foreground">{lang === "id" ? "Jejak semua aksi admin sensitif (login, ban, broadcast, approve, balance, provider)" : "Trail of all sensitive admin actions (login, ban, broadcast, approve, balance, provider)"}</p></div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />{lang === "id" ? "Refresh" : "Refresh"}</Button>
      </div>
      <Card>
        <CardHeader><CardTitle>{lang === "id" ? "Riwayat Aksi" : "Action History"} ({logs.length})</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-0 px-0 pt-0">
          {logs.length === 0 ? <p className="px-5 py-8 text-center text-sm text-muted-foreground">{loading ? "Memuat..." : lang === "id" ? "Belum ada log audit - setiap aksi kritis akan tercatat di sini" : "No audit logs yet — critical actions will appear here"}</p> : logs.map((l: any) => (
            <div key={l.id} className="flex items-start gap-3 border-b px-5 py-3 last:border-0 hover:bg-muted/30">
              <div className="mt-0.5 shrink-0">{actionBadge(l.action)}</div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap gap-2 text-sm"><span className="font-medium">{l.target || "-"}</span>{l.detail && <span className="text-muted-foreground truncate max-w-[500px]">{l.detail}</span>}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{new Date(l.ts).toLocaleString(lang === "id" ? "id-ID" : "en-US")} · {l.actor}</div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
