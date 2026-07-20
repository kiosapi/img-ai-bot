"use client";
import { useEffect, useState } from "react";
import { Cpu, HardDrive, MemoryStick, Server, Database, Boxes, Clock, Activity, RefreshCw, HardDriveIcon } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";

function Progress({ val, color = "bg-primary" }: { val: number; color?: string }) {
  return <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden"><div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(100, Math.max(0, val))}%` }} /></div>;
}

export default function SystemPage() {
  const { lang } = useLang();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setErr(null);
    try { const d = await api("/api/system/stats"); setData(d); } catch (e: any) { setErr(String(e?.message || e)); } finally { setLoading(false); }
  }
  useEffect(() => { load(); const id = setInterval(load, 15000); return () => clearInterval(id); }, []);

  if (loading && !data) return <div className="py-20 text-center text-muted-foreground">Memuat sistem...</div>;
  if (err) return <div className="py-20 text-center text-destructive text-sm">{err} <div className="mt-2"><Button size="sm" onClick={load}>Retry</Button></div></div>;
  if (!data) return null;

  const cpu = data.cpu || {};
  const mem = data.memory || {};
  const disk = data.disk || {};
  const pg = data.postgres || {};
  const processesTop = data.processes_top || data.top_processes || [];
  const loadAvg = data.load || [];

  const uptimeH = (() => { const s = data.uptime_sec || 0; const h = Math.floor(s / 3600); const d = Math.floor(h / 24); if (d) return `${d}d ${h % 24}h`; return `${h}h ${Math.floor((s % 3600) / 60)}m`; })();

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><Server className="h-6 w-6" />{lang === "id" ? "System Monitor" : "System Monitor"}</h1><p className="text-sm text-muted-foreground">{lang === "id" ? "CPU, RAM, Disk, Postgres, proses — live seperti htop, tanpa buka VPS." : "CPU, RAM, Disk, Postgres, processes — like htop without SSH."}</p></div><Button variant="outline" size="sm" onClick={load}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button></div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card><CardHeader><CardTitle><Cpu className="h-4 w-4" />CPU — {cpu.percent ?? data.cpu_percent ?? 0}%</CardTitle></CardHeader><CardContent className="flex flex-col gap-2"><Progress val={cpu.percent ?? data.cpu_percent ?? 0} color={((cpu.percent ?? 0) > 80 ? "bg-red-500" : (cpu.percent ?? 0) > 60 ? "bg-amber-500" : "bg-emerald-500")} /><div className="text-xs text-muted-foreground flex justify-between"><span>{lang === "id" ? "Cores" : "Cores"}: {cpu.count || cpu.cores || "-"}</span><span>Load: {Array.isArray(loadAvg) ? loadAvg.map((x: number) => x.toFixed(2)).join(" ") : "-"}</span></div>{cpu.per_cpu && <div className="mt-1 grid grid-cols-4 gap-1">{cpu.per_cpu.map((p: number, i: number) => <div key={i} className="text-[11px]"><div className="text-muted-foreground">C{i}</div><Progress val={p} /></div>)}</div>}</CardContent></Card>
        <Card><CardHeader><CardTitle><MemoryStick className="h-4 w-4" />RAM — {mem.percent ?? 0}%</CardTitle></CardHeader><CardContent className="flex flex-col gap-2"><Progress val={mem.percent ?? 0} color={(mem.percent ?? 0) > 85 ? "bg-red-500" : "bg-blue-500"} /><div className="text-xs text-muted-foreground">{((mem.used ?? 0) / 1024 / 1024 / 1024).toFixed(2)} GB / {((mem.total ?? 0) / 1024 / 1024 / 1024).toFixed(2)} GB</div><div className="text-[11px] text-muted-foreground">Available: {((mem.available ?? 0) / 1024 / 1024 / 1024).toFixed(2)} GB · Swap {mem.swap_percent ?? 0}%</div></CardContent></Card>
        <Card><CardHeader><CardTitle><HardDrive className="h-4 w-4" />Disk — {disk.percent ?? 0}%</CardTitle></CardHeader><CardContent className="flex flex-col gap-2"><Progress val={disk.percent ?? 0} color={(disk.percent ?? 0) > 90 ? "bg-red-500" : "bg-violet-500"} /><div className="text-xs text-muted-foreground">{((disk.used ?? 0) / 1024 / 1024 / 1024).toFixed(1)} GB / {((disk.total ?? 0) / 1024 / 1024 / 1024).toFixed(1)} GB</div><div className="text-[11px] text-muted-foreground flex gap-2"><span><Clock className="inline h-3 w-3" /> Uptime {uptimeH}</span><span>· {data.hostname || "-"}</span></div></CardContent></Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card><CardHeader><CardTitle><Database className="h-4 w-4" />Postgres — {pg.db_size_human || "-"}</CardTitle></CardHeader><CardContent className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2 text-xs"><div>DB size: <b>{pg.db_size_human || "-"}</b></div><div>Connections: {pg.pg_stat_activity_count ?? "-"} / {pg.pg_max_connections ?? "-"}</div></div>
          {pg.row_counts && <div className="grid grid-cols-2 gap-2 text-[12px]">{Object.entries(pg.row_counts).map(([k, v]: any) => <div key={k} className="flex justify-between border-b py-1"><span className="text-muted-foreground">{k}</span><Badge variant="muted">{String(v)}</Badge></div>)}</div>}
          {pg.tables && Array.isArray(pg.tables) && pg.tables.length > 0 && <div className="mt-2"><div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Top tables by size</div><div className="flex flex-col gap-1 text-[11px]">{pg.tables.slice(0, 10).map((t: any, i: number) => <div key={i} className="flex justify-between"><span>{t.relname || t.name || t.table || "-"}</span><span className="text-muted-foreground">{t.size_human || t.pg_size_pretty || t.size || ""}</span></div>)}</div></div>}
        </CardContent></Card>

        <Card><CardHeader><CardTitle><Boxes className="h-4 w-4" />{Array.isArray(data.docker_containers) && data.docker_containers.length ? "Docker" : "Top Processes"}</CardTitle></CardHeader><CardContent className="flex flex-col gap-1">
          {(data.docker_containers || []).length > 0 ? (data.docker_containers as any[]).map((c: any, i: number) => <div key={i} className="flex justify-between text-xs border-b py-1.5"><span className="truncate">{c.Names || c.names || c.name || c.Id || c.id || String(c).slice(0, 40)}</span><span className="text-muted-foreground">{c.Status || c.status || ""}</span></div>) : processesTop.map((p: any, i: number) => <div key={i} className="flex justify-between text-xs border-b py-1.5"><span className="truncate flex-1">{p.name || p.cmd || "-"}</span><span className="ml-2 text-muted-foreground">CPU {p.cpu_percent ?? p.cpu ?? 0}% MEM {(p.memory_percent ?? p.mem ?? 0).toFixed?.(1) ?? p.memory_percent ?? 0}%</span></div>)}
          {!(data.docker_containers?.length) && processesTop.length === 0 && <div className="py-6 text-center text-xs text-muted-foreground">No process info</div>}
        </CardContent></Card>
      </div>

      <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground flex items-center gap-2"><Activity className="h-3.5 w-3.5" />Auto refresh 15s · API <code>/api/system/stats</code> · Source: psutil non-blocking executor · no secrets leaked</div>
    </div>
  );
}
