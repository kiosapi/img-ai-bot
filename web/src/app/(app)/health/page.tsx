"use client";
import { useEffect, useState } from "react";
import { Bot, HeartPulse, Users, Image as ImageIcon, AlertTriangle, RefreshCw, Power, Zap, Timer, Layers, CheckCircle2, XCircle } from "lucide-react";
import { PageLoader } from "@/components/ui/page-loader";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";
import { toast } from "sonner";

export default function HealthPage() {
  const { lang, t } = useLang();
  const [bot, setBot] = useState<any>(null);
  const [providers, setProviders] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [restartOpen, setRestartOpen] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [b, p] = await Promise.all([api("/api/health/bot"), api("/api/health/providers")]);
      setBot(b); setProviders(p); setLastUpdate(new Date());
    } catch (e: any) { toast.error(String(e?.message || e)); } finally { setLoading(false); }
  }
  useEffect(() => { load(); const id = setInterval(() => load(), 10000); return () => clearInterval(id); }, []);

  async function doRestart(mode: "flag" | "docker") {
    setRestarting(true);
    try {
      const r = await api("/api/system/restart-bot", { method: "POST", body: JSON.stringify({ reason: `admin dashboard restart ${mode}`, mode }) });
      toast.success(`${mode} restart: flag=${r.flag_written} docker_ok=${r.docker_ok} ${r.details?.join("; ") || ""}`);
    } catch (e: any) { toast.error(e.message || "Restart failed"); } finally { setRestarting(false); setRestartOpen(false); }
  }

  if (loading && !bot) return <PageLoader label={lang === "id" ? "Memuat..." : "Loading..."} cards={3} rows={4} />;

  const online = bot?.online;

  return (
    <div className="flex flex-col gap-4 w-full max-w-full overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 w-full">
        <div className="min-w-0"><h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2"><HeartPulse className="h-5 w-5 sm:h-6 sm:w-6" />{lang === "id" ? "Bot Health Center" : "Bot Health Center"}</h1><p className="text-xs sm:text-sm text-muted-foreground mt-1 flex flex-wrap items-center gap-2"><span className="inline-flex items-center gap-1"><span className={`h-2 w-2 rounded-full ${online ? "bg-emerald-500 animate-pulse" : "bg-red-500"}`} />{online ? (lang === "id" ? "ONLINE REALTIME" : "ONLINE REALTIME") : (lang === "id" ? "OFFLINE" : "OFFLINE")}</span>· heartbeat 60s · {lastUpdate ? lastUpdate.toLocaleTimeString(lang === "id" ? "id-ID" : "en-US") : "-"} · auto 10s</p></div>
        <div className="flex gap-2 shrink-0"><Button variant="outline" size="sm" onClick={load} className="h-8 text-xs"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />{lang === "id" ? "Refresh" : "Refresh"}</Button><Button variant="outline" size="sm" onClick={() => setRestartOpen(true)} className="h-8 text-xs"><Power className="h-4 w-4" />Restart</Button></div>
      </div>

      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4 w-full">
        <Card className={`w-full overflow-hidden ${online ? "border-emerald-500/30" : "border-red-500/30"}`}><CardHeader className="pb-1"><CardTitle className="text-xs sm:text-sm"><Bot className="h-4 w-4" />{lang === "id" ? "Status Bot" : "Bot Status"}</CardTitle></CardHeader><CardContent><div className={`text-lg sm:text-2xl font-bold flex items-center gap-2 ${online ? "text-emerald-500" : "text-destructive"}`}><span className={`h-2.5 w-2.5 rounded-full ${online ? "bg-emerald-500 animate-pulse" : "bg-red-500"}`} />{online ? "Online" : "Offline"}</div><div className="text-[11px] sm:text-xs text-muted-foreground mt-1 break-all">{lang === "id" ? "heartbeat" : "heartbeat"} {bot?.heartbeat_age_sec != null ? `${bot.heartbeat_age_sec}s ago` : "-"} · {bot?.heartbeat_at ? new Date(bot.heartbeat_at).toLocaleString(lang === "id" ? "id-ID" : "en-US") : (lang === "id" ? "belum ada heartbeat" : "no heartbeat yet")}</div></CardContent></Card>
        <Card className="w-full overflow-hidden"><CardHeader className="pb-1"><CardTitle className="text-xs sm:text-sm"><Timer className="h-4 w-4" />{lang === "id" ? "Gen / jam" : "Gen / hour"}</CardTitle></CardHeader><CardContent><div className="text-2xl sm:text-3xl font-extrabold">{bot?.gen_per_hour ?? 0}</div><div className="text-[11px] sm:text-xs text-muted-foreground mt-1">{lang === "id" ? "Hari ini" : "Today"} {bot?.today_gen ?? 0} · total {bot?.total_users ?? 0} users</div></CardContent></Card>
        <Card className="w-full overflow-hidden"><CardHeader className="pb-1"><CardTitle className="text-xs sm:text-sm"><Users className="h-4 w-4" />{lang === "id" ? "Aktif 5m" : "Active 5m"}</CardTitle></CardHeader><CardContent><div className="text-2xl sm:text-3xl font-extrabold">{bot?.active_users_5m ?? 0}</div><div className="text-[11px] sm:text-xs text-muted-foreground mt-1">{lang === "id" ? "User gen 5m terakhir" : "Users gen last 5m"} · REALTIME DB query</div></CardContent></Card>
        <Card className={`w-full overflow-hidden ${(bot?.queue_stuck_count ?? 0) > 0 ? "border-amber-500/30" : ""}`}><CardHeader className="pb-1"><CardTitle className="text-xs sm:text-sm"><Layers className="h-4 w-4" />{lang === "id" ? "Stuck Queue" : "Stuck Queue"}</CardTitle></CardHeader><CardContent><div className="text-2xl sm:text-3xl font-extrabold">{bot?.queue_stuck_count ?? 0}</div><div className="text-[11px] sm:text-xs text-muted-foreground mt-1 flex items-center gap-1">{(bot?.queue_stuck_count ?? 0) > 0 ? "FSM >5m · needs action" : (lang === "id" ? <><CheckCircle2 className="inline h-3 w-3 text-emerald-500" /> tidak ada stuck</> : <><CheckCircle2 className="inline h-3 w-3 text-emerald-500" /> no stuck</>)} · REALTIME</div></CardContent></Card>
      </div>

      <Card className="w-full overflow-hidden"><CardHeader className="pb-2"><CardTitle className="text-sm"><ImageIcon className="h-4 w-4" />{lang === "id" ? "Generasi Terbaru" : "Latest Generation"} <Badge variant="muted" className="ml-2 text-[10px]">REALTIME DB</Badge></CardTitle></CardHeader><CardContent className="text-sm w-full overflow-hidden">{bot?.last_generation ? <div className="flex flex-col gap-1 w-full"><div className="flex gap-2 flex-wrap items-center"><Badge variant="muted" className="text-[11px]">ID {bot.last_generation.id}</Badge><Badge variant={bot.last_generation.success ? "muted" : "destructive"} className="text-[11px] flex items-center gap-1">{bot.last_generation.success ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{bot.last_generation.success ? "success" : "fail"}</Badge><span className="text-muted-foreground text-xs break-all">user {bot.last_generation.user_id} · {bot.last_generation.kind}</span></div><div className="text-xs text-muted-foreground break-all">{bot.last_generation.created_at ? new Date(bot.last_generation.created_at).toLocaleString(lang === "id" ? "id-ID" : "en-US") : ""} · {bot.last_generation.prompt?.slice?.(0, 80) || ""}</div></div> : <span className="text-muted-foreground text-sm">{lang === "id" ? "Belum ada generasi" : "No generations yet"}</span>}</CardContent></Card>

      <Card className="w-full overflow-hidden"><CardHeader className="pb-2"><CardTitle className="text-sm"><Zap className="h-4 w-4" />{lang === "id" ? "Latensi Provider" : "Provider Latency"} <Badge variant="muted" className="ml-2 text-[10px]">REALTIME PING · cache 30s · no key leak</Badge></CardTitle></CardHeader><CardContent className="flex flex-col gap-0 px-0 pt-0 w-full">
        {(!providers?.providers || providers.providers.length === 0) && <div className="py-6 text-center text-sm text-muted-foreground">{lang === "id" ? "Tidak ada provider" : "No providers"}</div>}
        {providers?.providers?.map((p: any) => (
          <div key={p.id} className="flex items-center gap-2 sm:gap-3 border-b px-3 sm:px-5 py-3 last:border-0 w-full overflow-hidden">
            <div className={`h-2.5 w-2.5 rounded-full shrink-0 ${p.ok ? "bg-emerald-500" : "bg-red-500"}`} />
            <div className="min-w-0 flex-1 overflow-hidden"><div className="flex gap-2 items-center flex-wrap"><span className="font-medium text-sm">{p.id}</span><Badge variant={p.is_active ? "muted" : "destructive"} className="text-[10px]">{p.is_active ? "active" : "off"}</Badge><span className="text-[11px] text-muted-foreground">{p.models_active}/{p.models_total} models</span></div><div className="text-[11px] text-muted-foreground truncate">{p.resolved_base_url || p.base_url}</div></div>
            <div className="text-right shrink-0"><div className={`text-sm font-medium ${p.latency_ms == null ? "text-muted-foreground" : p.latency_ms > 2000 ? "text-amber-500" : "text-emerald-500"}`}>{p.latency_ms != null ? `${p.latency_ms}ms` : "—"}</div><div className="text-[10px] sm:text-[11px] text-muted-foreground max-w-[120px] truncate">{p.ok ? `HTTP ${p.status_code}` : p.error?.slice(0, 60)}</div></div>
          </div>
        ))}
        {providers?.checked_at && <div className="px-3 sm:px-5 py-2 text-[11px] text-muted-foreground break-all">{lang === "id" ? "Dicek" : "Checked"} {new Date(providers.checked_at).toLocaleString(lang === "id" ? "id-ID" : "en-US")} · {lang === "id" ? "ping real tanpa kirim API key" : "real ping without API key"}</div>}
      </CardContent></Card>

      <ConfirmDialog open={restartOpen} onClose={() => setRestartOpen(false)} title={lang === "id" ? "Restart Bot?" : "Restart Bot?"} description={`${lang === "id" ? "Pilih mode restart: flag (aman, watcher akan restart) atau docker (langsung docker restart container). Semua 100% akurat, tanpa SSH." : "Choose restart mode: flag (safe) or docker (direct container restart). 100% accurate, no SSH."}`} confirmLabel={lang === "id" ? "Restart Flag" : "Restart Flag"} variant="destructive" loading={restarting} onConfirm={() => doRestart("flag")} />

      <div className="rounded-lg border border-dashed p-2.5 sm:p-3 text-[11px] sm:text-xs text-muted-foreground flex flex-wrap items-center gap-2"><AlertTriangle className="h-3.5 w-3.5 shrink-0" /><span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />{lang === "id" ? "REALTIME 10s" : "REALTIME 10s"}</span>· Bot heartbeat 60s settings table · offline &gt;120s · provider ping GET base_url 6s timeout no key · restart flag /tmp + docker · 100% akurat data live, bukan fake.</div>
    </div>
  );
}
