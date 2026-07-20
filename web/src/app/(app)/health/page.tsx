"use client";
import { useEffect, useState } from "react";
import { Bot, HeartPulse, Clock3, Users, Image as ImageIcon, AlertTriangle, RefreshCw, Power, Zap, Timer, Layers } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";
import { toast } from "sonner";

export default function HealthPage() {
  const { lang } = useLang();
  const [bot, setBot] = useState<any>(null);
  const [providers, setProviders] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [restartOpen, setRestartOpen] = useState(false);
  const [restarting, setRestarting] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [b, p] = await Promise.all([api("/api/health/bot"), api("/api/health/providers")]);
      setBot(b); setProviders(p);
    } catch (e: any) { toast.error(String(e?.message || e)); } finally { setLoading(false); }
  }
  useEffect(() => { load(); const id = setInterval(load, 15000); return () => clearInterval(id); }, []);

  async function doRestart(mode: "flag" | "docker") {
    setRestarting(true);
    try {
      const r = await api("/api/system/restart-bot", { method: "POST", body: JSON.stringify({ reason: `admin dashboard restart ${mode}`, mode }) });
      toast.success(`${mode} restart: flag=${r.flag_written} docker_ok=${r.docker_ok} ${r.details?.join("; ") || ""}`);
    } catch (e: any) { toast.error(e.message || "Restart failed"); } finally { setRestarting(false); setRestartOpen(false); }
  }

  if (loading && !bot) return <div className="py-20 text-center text-muted-foreground">Memuat health...</div>;

  const online = bot?.online;
  const age = bot?.heartbeat_age_sec;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><HeartPulse className="h-6 w-6" />{lang === "id" ? "Bot Health Center" : "Bot Health Center"}</h1><p className="text-sm text-muted-foreground">{lang === "id" ? "Status polling, heartbeat, generasi terbaru, provider latency, tombol restart — semua tanpa buka VPS." : "Polling status, heartbeat, latest gen, provider latency, restart button — no SSH."}</p></div><div className="flex gap-2"><Button variant="outline" size="sm" onClick={load}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button><Button variant="outline" size="sm" onClick={() => setRestartOpen(true)}><Power className="h-4 w-4" />Restart</Button></div></div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card className={online ? "border-emerald-500/30" : "border-red-500/30"}><CardHeader><CardTitle><Bot className="h-4 w-4" />Status</CardTitle></CardHeader><CardContent><div className={`text-2xl font-bold flex items-center gap-2 ${online ? "text-emerald-500" : "text-destructive"}`}><span className={`h-2.5 w-2.5 rounded-full ${online ? "bg-emerald-500 animate-pulse" : "bg-red-500"}`} />{online ? "Online" : "Offline"}</div><div className="text-xs text-muted-foreground mt-1">heartbeat {age != null ? `${age}s ago` : "-"} · {bot?.heartbeat_at ? new Date(bot.heartbeat_at).toLocaleString(lang === "id" ? "id-ID" : "en-US") : "no heartbeat yet"}</div></CardContent></Card>
        <Card><CardHeader><CardTitle><Timer className="h-4 w-4" />Gen / jam</CardTitle></CardHeader><CardContent><div className="text-3xl font-extrabold">{bot?.gen_per_hour ?? 0}</div><div className="text-xs text-muted-foreground mt-1">{lang === "id" ? "Hari ini" : "Today"} {bot?.today_gen ?? 0} · total {bot?.total_users ?? 0} users</div></CardContent></Card>
        <Card><CardHeader><CardTitle><Users className="h-4 w-4" />Aktif 5m</CardTitle></CardHeader><CardContent><div className="text-3xl font-extrabold">{bot?.active_users_5m ?? 0}</div><div className="text-xs text-muted-foreground mt-1">{lang === "id" ? "User generate 5 menit terakhir" : "Users generating last 5m"}</div></CardContent></Card>
        <Card className={(bot?.queue_stuck_count ?? 0) > 0 ? "border-amber-500/30" : ""}><CardHeader><CardTitle><Layers className="h-4 w-4" />Stuck queue</CardTitle></CardHeader><CardContent><div className="text-3xl font-extrabold">{bot?.queue_stuck_count ?? 0}</div><div className="text-xs text-muted-foreground mt-1">{(bot?.queue_stuck_count ?? 0) > 0 ? "FSM states >5m" : "congrats, no stuck"}</div></CardContent></Card>
      </div>

      <Card><CardHeader><CardTitle><ImageIcon className="h-4 w-4" />{lang === "id" ? "Gen Terbaru" : "Latest Generation"}</CardTitle></CardHeader><CardContent className="text-sm">{bot?.last_generation ? <div className="flex flex-col gap-1"><div className="flex gap-2 flex-wrap"><Badge variant="muted">ID {bot.last_generation.id}</Badge><Badge variant={bot.last_generation.success ? "muted" : "destructive"}>{bot.last_generation.success ? "success" : "fail"}</Badge><span className="text-muted-foreground">user {bot.last_generation.user_id} · {bot.last_generation.kind}</span></div><div className="text-xs text-muted-foreground">{bot.last_generation.created_at ? new Date(bot.last_generation.created_at).toLocaleString(lang === "id" ? "id-ID" : "en-US") : ""}</div></div> : <span className="text-muted-foreground text-sm">Belum ada generasi</span>}</CardContent></Card>

      <Card><CardHeader><CardTitle><Zap className="h-4 w-4" />Provider Latency</CardTitle></CardHeader><CardContent className="flex flex-col gap-0 px-0 pt-0">
        {(!providers?.providers || providers.providers.length === 0) && <div className="py-6 text-center text-sm text-muted-foreground">No providers</div>}
        {providers?.providers?.map((p: any) => (
          <div key={p.id} className="flex items-center gap-3 border-b px-5 py-3 last:border-0">
            <div className={`h-2.5 w-2.5 rounded-full ${p.ok ? "bg-emerald-500" : "bg-red-500"}`} />
            <div className="min-w-0 flex-1"><div className="flex gap-2 items-center"><span className="font-medium">{p.id}</span><Badge variant={p.is_active ? "muted" : "destructive"}>{p.is_active ? "active" : "off"}</Badge><span className="text-xs text-muted-foreground">{p.models_active}/{p.models_total} models</span></div><div className="text-xs text-muted-foreground truncate">{p.resolved_base_url || p.base_url}</div></div>
            <div className="text-right"><div className={`text-sm font-medium ${p.latency_ms == null ? "text-muted-foreground" : p.latency_ms > 2000 ? "text-amber-500" : "text-emerald-500"}`}>{p.latency_ms != null ? `${p.latency_ms}ms` : "—"}</div><div className="text-[11px] text-muted-foreground">{p.ok ? `HTTP ${p.status_code}` : p.error?.slice(0, 60)}</div></div>
          </div>
        ))}
        {providers?.checked_at && <div className="px-5 py-2 text-[11px] text-muted-foreground">{lang === "id" ? "Dicek" : "Checked"} {new Date(providers.checked_at).toLocaleTimeString()} · cache 30s</div>}
      </CardContent></Card>

      <ConfirmDialog open={restartOpen} onClose={() => setRestartOpen(false)} title={lang === "id" ? "Restart Bot?" : "Restart Bot?"} description={`${lang === "id" ? "Pilih mode restart" : "Choose restart mode"}: flag (aman, watcher akan restart) atau docker (langsung docker restart container).`} confirmLabel={lang === "id" ? "Restart Flag" : "Restart Flag"} variant="destructive" loading={restarting} onConfirm={() => doRestart("flag")} />

      <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground flex items-center gap-2"><AlertTriangle className="h-3.5 w-3.5" />Bot heartbeat update tiap 60s via settings table. Offline kalau heartbeat &gt;120s. Provider ping GET base_url 6s timeout no key leaked. Restart flag file /tmp/imgbot_restart_bot.flag + optional ENABLE_DOCKER_RESTART=1.</div>
    </div>
  );
}
