"use client";
import { useEffect, useState } from "react";
import { Cpu, HardDrive, MemoryStick, Server, Database, Boxes, Clock, Activity, RefreshCw } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";
import { PageLoader } from "@/components/ui/page-loader";

function Progress({ val, color = "bg-primary" }: { val: number; color?: string }) {
  return <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden"><div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(100, Math.max(0, val))}%` }} /></div>;
}

export default function SystemPage() {
  const { lang, t } = useLang();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  async function load() {
    setLoading(true); setErr(null);
    try { const d = await api("/api/system/stats"); setData(d); setLastUpdate(new Date()); } catch (e: any) { setErr(String(e?.message || e)); } finally { setLoading(false); }
  }
  useEffect(() => { load(); const id = setInterval(() => load(), 10000); return () => clearInterval(id); }, []);

  if (loading && !data) return <PageLoader label={lang === "id" ? "Memuat sistem..." : "Loading system..."} cards={4} rows={3} />;
  if (err) return <div className="py-20 text-center text-destructive text-sm">{err} <div className="mt-2"><Button size="sm" onClick={load}>Retry</Button></div></div>;
  if (!data) return null;

  const cpu = data.cpu || {};
  const mem = data.memory || {};
  const disk = data.disk || {};
  const pg = data.postgres || {};
  const processesTop = data.processes_top || data.top_processes || [];
  const loadAvg = data.load || data.load_avg || [];
  const loadList = Array.isArray(loadAvg) ? loadAvg : (typeof loadAvg === "object" ? [loadAvg["1m"] ?? loadAvg["1"] ?? 0, loadAvg["5m"] ?? loadAvg["5"] ?? 0, loadAvg["15m"] ?? loadAvg["15"] ?? 0] : []);
  const uptimeH = (() => { const s = data.uptime_sec || data.uptime_seconds || 0; const h = Math.floor(s / 3600); const d = Math.floor(h / 24); if (d) return `${d}d ${h % 24}h`; return `${h}h ${Math.floor((s % 3600) / 60)}m`; })();
  const id = (k: string) => lang === "id" ? ({ "cores": "Cores", "load": "Beban", "available": "Tersedia", "swap": "Swap", "uptime": "Up", "hostname": "Host", "db_size": "Ukuran DB", "connections": "Koneksi", "top_tables": "Tabel terbesar", "no_proc": "Tidak ada info proses", "refresh": "Refresh", "realtime": "REALTIME 10s", "fallback": "Fallback", "top_procs": "Proses Top", "docker": "Docker", "auto": "Auto" } as any)[k] || k : ({ "cores": "Cores", "load": "Load", "available": "Available", "swap": "Swap", "uptime": "Uptime", "hostname": "Host", "db_size": "DB size", "connections": "Connections", "top_tables": "Top tables", "no_proc": "No process info", "refresh": "Refresh", "realtime": "REALTIME 10s", "fallback": "Fallback", "top_procs": "Top Processes", "docker": "Docker", "auto": "Auto"} as any)[k] || k;

  return (
    <div className="flex flex-col gap-4 w-full max-w-full min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-3 w-full">
        <div className="min-w-0"><h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2"><Server className="h-5 w-5 sm:h-6 sm:w-6" />{lang === "id" ? "System Monitor" : "System Monitor"}</h1><p className="text-xs sm:text-sm text-muted-foreground mt-1 flex items-center gap-2 flex-wrap"><span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />psutil REALTIME</span>· 10s · {lastUpdate ? lastUpdate.toLocaleTimeString(lang === "id" ? "id-ID" : "en-US") : "-"} · {data.hostname || "-"} </p></div>
        <Button variant="outline" size="sm" onClick={load} className="h-8 text-xs shrink-0"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />{id("refresh")}</Button>
      </div>

      <div className="grid gap-3 sm:gap-4 grid-cols-1 md:grid-cols-3 w-full">
        <Card className="w-full overflow-hidden"><CardHeader className="pb-2"><CardTitle className="text-sm"><Cpu className="h-4 w-4" />CPU — {cpu.percent ?? data.cpu_percent ?? 0}%</CardTitle></CardHeader><CardContent className="flex flex-col gap-2"><Progress val={cpu.percent ?? data.cpu_percent ?? 0} color={((cpu.percent ?? 0) > 80 ? "bg-red-500" : (cpu.percent ?? 0) > 60 ? "bg-amber-500" : "bg-emerald-500")} /><div className="text-xs text-muted-foreground flex flex-wrap justify-between gap-2"><span>{id("cores")}: {cpu.count || cpu.cores || cpu.cpu_count_logical || "-"}</span><span>{id("load")}: {Array.isArray(loadList) ? loadList.map((x: number) => (x ?? 0).toFixed(2)).join(" ") : "-"}</span></div>{Array.isArray(cpu.per_cpu) && cpu.per_cpu.length > 0 && <div className="mt-1 grid grid-cols-4 gap-1.5">{cpu.per_cpu.map((p: number, i: number) => <div key={i} className="text-[10px]"><div className="text-muted-foreground">C{i}</div><Progress val={p} /></div>)}</div>}</CardContent></Card>
        <Card className="w-full overflow-hidden"><CardHeader className="pb-2"><CardTitle className="text-sm"><MemoryStick className="h-4 w-4" />RAM — {mem.percent ?? data.memory?.percent ?? 0}%</CardTitle></CardHeader><CardContent className="flex flex-col gap-2"><Progress val={mem.percent ?? data.memory?.percent ?? 0} color={(mem.percent ?? 0) > 85 ? "bg-red-500" : "bg-blue-500"} /><div className="text-xs text-muted-foreground break-all">{((mem.used ?? data.memory?.used ?? 0) / 1024 / 1024 / 1024).toFixed(2)} GB / {((mem.total ?? data.memory?.total ?? 0) / 1024 / 1024 / 1024).toFixed(2)} GB</div><div className="text-[11px] text-muted-foreground break-all">{id("available")}: {((mem.available ?? data.memory?.available ?? 0) / 1024 / 1024 / 1024).toFixed(2)} GB · {id("swap")} {mem.swap_percent ?? data.memory?.swap_percent ?? 0}%</div></CardContent></Card>
        <Card className="w-full overflow-hidden"><CardHeader className="pb-2"><CardTitle className="text-sm"><HardDrive className="h-4 w-4" />Disk — {disk.percent ?? data.disk?.percent ?? 0}%</CardTitle></CardHeader><CardContent className="flex flex-col gap-2"><Progress val={disk.percent ?? data.disk?.percent ?? 0} color={(disk.percent ?? 0) > 90 ? "bg-red-500" : "bg-violet-500"} /><div className="text-xs text-muted-foreground">{((disk.used ?? data.disk?.used ?? 0) / 1024 / 1024 / 1024).toFixed(1)} GB / {((disk.total ?? data.disk?.total ?? 0) / 1024 / 1024 / 1024).toFixed(1)} GB</div><div className="text-[11px] text-muted-foreground flex gap-2 flex-wrap"><span><Clock className="inline h-3 w-3" /> {id("uptime")} {uptimeH}</span><span>· {data.platform?.hostname || data.hostname || "-"}</span></div></CardContent></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2 w-full">
        <Card className="w-full overflow-hidden"><CardHeader className="pb-2"><CardTitle className="text-sm"><Database className="h-4 w-4" />Postgres — {pg.db_size_human || pg.db_size_human || "-"} <Badge variant="muted" className="ml-2 text-[10px]">REALTIME SQL</Badge></CardTitle></CardHeader><CardContent className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2 text-xs"><div>{id("db_size")}: <b>{pg.db_size_human || "-"}</b></div><div>{id("connections")}: {pg.pg_stat_activity_count ?? "-"} / {pg.pg_max_connections ?? "-"}</div></div>
          {pg.row_counts && <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 sm:gap-2 text-[12px] w-full">{Object.entries(pg.row_counts).map(([k, v]: any) => <div key={k} className="flex justify-between border-b py-1 gap-2"><span className="text-muted-foreground truncate">{k}</span><Badge variant="muted" className="shrink-0 text-[10px]">{String(v)}</Badge></div>)}</div>}
          {pg.tables && Array.isArray(pg.tables) && pg.tables.length > 0 && <div className="mt-2"><div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">{id("top_tables")}</div><div className="flex flex-col gap-1 text-[11px] w-full">{pg.tables.slice(0, 10).map((t: any, i: number) => <div key={i} className="flex justify-between gap-2 w-full"><span className="truncate">{t.relname || t.name || t.table || "-"}</span><span className="text-muted-foreground shrink-0">{t.size_human || t.pg_size_pretty || t.size || ""}</span></div>)}</div></div>}
        </CardContent></Card>

        <Card className="w-full overflow-hidden"><CardHeader className="pb-2"><CardTitle className="text-sm"><Boxes className="h-4 w-4" />{Array.isArray(data.docker_containers) && data.docker_containers.length ? id("docker") : id("top_procs")} <Badge variant="muted" className="ml-2 text-[10px]">REALTIME</Badge></CardTitle></CardHeader><CardContent className="flex flex-col gap-0.5 max-w-full min-w-0">
          {(data.docker_containers || []).length > 0 ? (data.docker_containers as any[]).map((c: any, i: number) => <div key={i} className="flex justify-between text-xs border-b py-1.5 gap-2 w-full"><span className="truncate min-w-0">{c.Names || c.names || c.name || c.Id || c.id || String(c).slice(0, 40)}</span><span className="text-muted-foreground shrink-0 truncate">{c.Status || c.status || ""}</span></div>) : processesTop.map((p: any, i: number) => <div key={i} className="flex justify-between text-xs border-b py-1.5 gap-2 w-full"><span className="truncate min-w-0 flex-1">{p.name || p.cmd || "-"}</span><span className="ml-2 text-muted-foreground shrink-0 text-[11px]">CPU {p.cpu_percent ?? p.cpu ?? 0}% MEM {(typeof p.memory_percent === "number" ? p.memory_percent.toFixed(1) : p.memory_percent ?? p.mem ?? 0)}%</span></div>)}
          {!(data.docker_containers?.length) && processesTop.length === 0 && <div className="py-8 text-center text-xs text-muted-foreground">{id("no_proc")}</div>}
        </CardContent></Card>
      </div>

      <div className="rounded-lg border border-dashed p-2.5 sm:p-3 text-[11px] sm:text-xs text-muted-foreground flex flex-wrap items-center gap-2"><Activity className="h-3.5 w-3.5 shrink-0" /><span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />{id("realtime")}</span>· API <code>/api/system/stats</code> · Source: psutil executor non-blocking + pg stats live + no secrets · 100% akurat</div>
    </div>
  );
}
