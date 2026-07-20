"use client";
import { useEffect, useState, useCallback, useMemo } from "react";
import {
  DollarSign, Wallet, TrendingUp, TrendingDown, RefreshCw, Banknote,
  BarChart3, Layers, Bot, Server, Zap, CheckCircle2, Activity, Save
} from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, Input } from "@/components/ui/controls";
import { CustomSelect } from "@/components/ui/modal";
import { useLang } from "@/lib/i18n";
import { toast } from "sonner";

type Daily = { date: string; day: string; gen_count: number; success: number; failed: number; revenue: number; cost: number; profit: number; };
type ProviderBreakdown = { id: string; name: string; is_active: boolean; cost_per_gen: number; gen_count: number; success: number; failed: number; success_rate: number; total_cost: number; };
type ModelBreakdown = { model_id: string; display_name: string; provider_id: string; cost_per_gen: number; gen_count: number; success: number; failed: number; success_rate: number; total_cost: number; };
type CostStats = {
  period: string; days: number;
  totals: {
    total_cost: number; total_revenue: number; total_profit: number; total_gens: number; total_success: number; total_failed: number; avg_cost_per_gen: number;
    deposit_revenue: number; order_revenue: number;
    most_expensive_provider: { id: string; name: string; cost_per_gen: number } | null;
    cheapest_provider: { id: string; name: string; cost_per_gen: number } | null;
    highest_usage_provider: { id: string; name: string; gen_count: number } | null;
  };
  daily: Daily[]; provider_breakdown: ProviderBreakdown[]; model_breakdown: ModelBreakdown[];
};

const PERIOD_OPTS = [
  { value: "7d", label: "7 hari / 7 days" },
  { value: "30d", label: "30 hari / 30 days" },
  { value: "90d", label: "90 hari / 90 days" },
  { value: "365d", label: "365 hari / 365 days" },
];

function fmtMoney(n: number): string {
  if (n == null || isNaN(n)) return "Rp 0";
  if (Math.abs(n) >= 1_000_000) return "Rp " + (n / 1_000_000).toFixed(2) + "M";
  if (Math.abs(n) >= 1_000) return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
  return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
}
function fmtNum(n: number | null | undefined, dec = 0): string {
  if (n == null || isNaN(n)) return "0";
  if (dec === 0) return Math.round(n).toLocaleString("id-ID");
  return n.toLocaleString("id-ID", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function MiniBarChart({ data }: { data: Daily[] }) {
  const maxVal = useMemo(() => {
    let mx = 1;
    for (const d of data) mx = Math.max(mx, d.revenue || 0, d.cost || 0, Math.abs(d.profit || 0));
    return mx;
  }, [data]);
  if (!data.length) return <div className="py-10 text-center text-sm text-muted-foreground">No data</div>;
  return (
    <div className="w-full overflow-hidden">
      <div className="flex gap-3 text-[11px] text-muted-foreground mb-2 flex-wrap">
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-emerald-500" /> Revenue</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-amber-500" /> Cost</span>
        <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-violet-500" /> Profit</span>
      </div>
      <div className="w-full overflow-x-auto scrollbar-thin pb-1">
        <div className="flex items-end gap-[3px] min-h-[130px] h-[150px] border-b border-l px-1 pb-1" style={{ minWidth: Math.max(320, data.length * 16) + "px" }}>
          {data.map((d, i) => {
            const revH = Math.max(3, Math.round(((d.revenue || 0) / maxVal) * 120));
            const costH = Math.max(3, Math.round(((d.cost || 0) / maxVal) * 120));
            const profH = Math.max(3, Math.round((Math.abs(d.profit || 0) / maxVal) * 100));
            const pos = (d.profit || 0) >= 0;
            return (
              <div key={i} className="flex flex-1 flex-col items-center justify-end gap-[2px] min-w-0">
                <div className="flex items-end gap-[2px]"><div className="w-[5px] rounded-t bg-emerald-500/80" style={{ height: revH + "px" }} title={`${d.date} rev`} /><div className="w-[5px] rounded-t bg-amber-500/80" style={{ height: costH + "px" }} title={`${d.date} cost`} /><div className={`w-[5px] rounded-t ${pos ? "bg-violet-500/80" : "bg-red-500/80"}`} style={{ height: profH + "px" }} title={`${d.date} profit`} /></div>
                <span className="text-[8px] text-muted-foreground truncate w-full text-center leading-none mt-1">{d.day.slice(0, 3)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function CostPage() {
  const { t, lang } = useLang();
  const [period, setPeriod] = useState("30d");
  const [stats, setStats] = useState<CostStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingCost, setEditingCost] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try { const res = (await api(`/api/cost/stats?period=${period}`)) as CostStats; setStats(res); }
    catch (e: any) { setErr(e?.message || "Gagal memuat cost"); }
    finally { setLoading(false); }
  }, [period]);
  useEffect(() => { load(); }, [load]);

  const startEdit = (p: ProviderBreakdown) => { setEditingId(p.id); setEditingCost(String(p.cost_per_gen ?? 0)); };
  const saveEdit = async (pid: string) => {
    const v = parseFloat(editingCost);
    if (isNaN(v) || v < 0 || v > 100000) { toast.error("cost 0-100000"); return; }
    setSavingEdit(true);
    try {
      await api(`/api/cost/providers/${pid}`, { method: "PUT", body: JSON.stringify({ cost_per_gen: v }) });
      toast.success(lang === "id" ? "Biaya disimpan" : "Cost saved");
      setEditingId(null); await load();
    } catch (e: any) { toast.error(e?.message || "Gagal simpan"); }
    finally { setSavingEdit(false); }
  };

  if (loading && !stats)
    return <div className="py-20 text-center text-sm text-muted-foreground flex flex-col gap-2 items-center"><RefreshCw className="h-5 w-5 animate-spin" />{t("common.loading")}</div>;
  if (err)
    return <div className="py-20 text-center text-sm"><div className="text-destructive">{err}</div><div className="mt-3"><Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4" />Retry</Button></div></div>;
  if (!stats) return null;

  const totals = stats.totals, daily = stats.daily || [], provs = stats.provider_breakdown || [], models = stats.model_breakdown || [];
  const totalRev = totals.total_revenue || 0, totalCost = totals.total_cost || 0, totalProfit = totals.total_profit || 0;
  const pos = totalProfit >= 0;
  const mostExpId = totals.most_expensive_provider?.id, cheapId = totals.cheapest_provider?.id, topId = totals.highest_usage_provider?.id;

  return (
    <div className="flex flex-col gap-5 w-full max-w-full overflow-hidden">
      {/* header — MATCH system page */}
      <div className="flex flex-wrap items-start justify-between gap-3 w-full">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2"><DollarSign className="h-5 w-5 sm:h-6 sm:w-6" />{t("cost.title")}</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">{t("cost.sub")}</p>
        </div>
        <div className="flex items-end gap-2 shrink-0">
          <div className="flex flex-col gap-1">
            <span className="text-[11px] text-muted-foreground uppercase tracking-wide">{t("cost.period")}</span>
            <CustomSelect value={period} onChange={setPeriod} options={PERIOD_OPTS} className="w-[170px]" />
          </div>
          <Button variant="outline" size="sm" onClick={load} disabled={loading} className="h-9 text-xs"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />{t("cost.refresh")}</Button>
        </div>
      </div>

      {/* stats cards — MATCH analytics dashboard */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 w-full">
        <Card className="w-full overflow-hidden">
          <CardHeader><CardTitle><Banknote className="h-4 w-4" />{t("cost.total_cost")} · {stats.days}D</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            <div className="text-2xl font-bold tracking-tight">{fmtMoney(totalCost)}</div>
            <div className="text-xs text-muted-foreground">{fmtNum(totals.total_gens, 0)} gens · {fmtNum(totals.avg_cost_per_gen, 4)} {t("cost.avg_cost_gen")}</div>
          </CardContent>
        </Card>
        <Card className="w-full overflow-hidden">
          <CardHeader><CardTitle><Wallet className="h-4 w-4" />{t("cost.total_revenue")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            <div className="text-2xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400">{fmtMoney(totalRev)}</div>
            <div className="text-xs text-muted-foreground">{t("cost.deposit_rev")} {fmtMoney(totals.deposit_revenue)} · {t("cost.order_rev")} {fmtMoney(totals.order_revenue)}</div>
          </CardContent>
        </Card>
        <Card className="w-full overflow-hidden">
          <CardHeader><CardTitle>{pos ? <TrendingUp className="h-4 w-4 text-violet-600" /> : <TrendingDown className="h-4 w-4 text-red-600" />}{t("cost.profit")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            <div className={`text-2xl font-bold tracking-tight ${pos ? "text-violet-600 dark:text-violet-400" : "text-red-600"}`}>{pos ? "+" : ""}{fmtMoney(totalProfit)}</div>
            <div className="text-xs text-muted-foreground">margin {totalRev > 0 ? ((totalProfit / totalRev) * 100).toFixed(1) : "0"}% · {fmtNum(totals.total_gens, 0)} gens · <span className={pos ? "text-emerald-600" : "text-red-600"}>{pos ? t("cost.profit_positive") : t("cost.profit_negative")}</span></div>
          </CardContent>
        </Card>
        <Card className="w-full overflow-hidden">
          <CardHeader><CardTitle><BarChart3 className="h-4 w-4" />{t("cost.total_gens")} · Success</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            <div className="text-2xl font-bold tracking-tight">{fmtNum(totals.total_gens, 0)}</div>
            <div className="text-xs text-muted-foreground flex flex-wrap gap-2"><span className="text-emerald-600">{fmtNum(totals.total_success, 0)} ok</span><span className="text-red-500">{fmtNum(totals.total_failed, 0)} fail</span>· {totals.total_gens > 0 ? ((totals.total_success / totals.total_gens) * 100).toFixed(1) : "0"}%</div>
          </CardContent>
        </Card>
      </div>

      {/* badges provider highlight */}
      <div className="flex flex-wrap gap-2">
        {totals.most_expensive_provider && <Badge variant="destructive" className="text-[11px] gap-1"><DollarSign className="h-3 w-3" />{t("cost.most_exp")}: {totals.most_expensive_provider.name} · {fmtNum(totals.most_expensive_provider.cost_per_gen, 4)}</Badge>}
        {totals.cheapest_provider && <Badge variant="outline" className="text-[11px] gap-1 border-emerald-200 text-emerald-700 dark:text-emerald-300"><CheckCircle2 className="h-3 w-3" />{t("cost.cheapest")}: {totals.cheapest_provider.name} · {fmtNum(totals.cheapest_provider.cost_per_gen, 4)}</Badge>}
        {totals.highest_usage_provider && <Badge variant="secondary" className="text-[11px] gap-1"><Zap className="h-3 w-3" />{t("cost.highest_usage")}: {totals.highest_usage_provider.name} · {fmtNum(totals.highest_usage_provider.gen_count, 0)}</Badge>}
      </div>

      {/* daily chart */}
      <Card className="w-full overflow-hidden">
        <CardHeader><CardTitle><Activity className="h-4 w-4" />{t("cost.daily_chart")} <Badge variant="secondary" className="ml-2 text-[11px]">{daily.length}d</Badge></CardTitle></CardHeader>
        <CardContent>
          {daily.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">{t("cost.no_data")}</div> : (
            <>
              <MiniBarChart data={daily} />
              <div className="mt-4 w-full overflow-x-auto"><table className="w-full text-xs min-w-[420px]"><thead className="border-b text-muted-foreground text-[11px]"><tr><th className="text-left py-1.5 px-2 font-medium">Date</th><th className="text-right px-2 py-1.5 font-medium">Gens</th><th className="text-right px-2 py-1.5 font-medium">Rev</th><th className="text-right px-2 py-1.5 font-medium">Cost</th><th className="text-right px-2 py-1.5 font-medium">Profit</th><th className="text-right px-2 py-1.5 font-medium">Ok/Fail</th></tr></thead><tbody className="divide-y">{daily.slice().reverse().slice(0, 30).map(d => <tr key={d.date} className="hover:bg-muted/50"><td className="py-2 px-2"><span className="font-medium">{d.date}</span> <span className="text-muted-foreground text-[11px]">{d.day}</span></td><td className="text-right px-2 py-2 font-mono text-[11px]">{fmtNum(d.gen_count, 0)}</td><td className="text-right px-2 py-2 font-mono text-emerald-600">{fmtMoney(d.revenue)}</td><td className="text-right px-2 py-2 font-mono text-amber-600">{fmtMoney(d.cost)}</td><td className={`text-right px-2 py-2 font-mono font-semibold ${d.profit >= 0 ? "text-violet-600" : "text-red-600"}`}>{fmtMoney(d.profit)}</td><td className="text-right px-2 py-2 text-[11px]"><span className="text-emerald-600">{d.success}</span>/<span className="text-red-500">{d.failed}</span></td></tr>)}</tbody></table></div>
            </>
          )}
        </CardContent>
      </Card>

      {/* provider breakdown */}
      <Card className="w-full overflow-hidden">
        <CardHeader><CardTitle><Server className="h-4 w-4" />{t("cost.provider_breakdown")} <Badge variant="secondary" className="ml-2 text-[11px]">{provs.length}</Badge></CardTitle></CardHeader>
        <CardContent className="p-0">
          {/* mobile cards */}
          <div className="flex flex-col gap-3 p-3 md:hidden w-full">
            {provs.map(p => {
              const maxCost = Math.max(...provs.map(x => x.total_cost), 1);
              const w = Math.max(4, (p.total_cost / maxCost) * 100);
              const isMost = p.id === mostExpId, isCheap = p.id === cheapId, isTop = p.id === topId;
              return (
                <div key={p.id} className={`rounded-lg border p-4 flex flex-col gap-2 w-full ${isMost ? "border-red-200 bg-red-50/40 dark:bg-red-950/20" : isCheap ? "border-emerald-200 bg-emerald-50/40 dark:bg-emerald-950/20" : "bg-card"}`}>
                  <div className="flex items-start justify-between gap-2"><div className="min-w-0"><div className="font-semibold text-sm flex items-center gap-1.5 truncate"><Server className="h-3.5 w-3.5 text-muted-foreground shrink-0" /><span className="truncate">{p.name}</span>{!p.is_active && <Badge variant="secondary" className="text-[9px]">off</Badge>}{isMost && <Badge variant="destructive" className="text-[8px] px-1">EXP</Badge>}{isCheap && <Badge variant="outline" className="text-[8px] px-1 border-emerald-300 text-emerald-700">CHEAP</Badge>}{isTop && <Badge variant="secondary" className="text-[8px] px-1">TOP</Badge>}</div><div className="text-[11px] text-muted-foreground mt-0.5">{p.id} · {p.success_rate}% ok</div></div><div className="text-right shrink-0"><div className={`font-mono text-sm font-bold ${isMost ? "text-red-600" : isCheap ? "text-emerald-600" : ""}`}>{fmtNum(p.cost_per_gen, 4)}</div><div className="text-[10px] text-muted-foreground">/gen</div></div></div>
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden"><div className="h-full bg-primary rounded-full" style={{ width: `${w}%` }} /></div>
                  <div className="flex justify-between text-xs"><span className="text-muted-foreground">{fmtNum(p.gen_count, 0)} gens · <span className="text-emerald-600">{p.success}</span>/<span className="text-red-500">{p.failed}</span> {p.success_rate}%</span><span className="font-bold">{fmtMoney(p.total_cost)}</span></div>
                  {editingId === p.id ? <div className="flex gap-1.5 pt-1"><Input className="h-8 flex-1 text-xs" value={editingCost} onChange={e => setEditingCost(e.target.value)} type="number" min={0} max={100000} step={0.0001} /><Button size="sm" className="h-8 text-xs" onClick={() => saveEdit(p.id)} disabled={savingEdit}><Save className="h-3 w-3" />{t("cost.save")}</Button><Button size="sm" variant="ghost" className="h-8 text-xs" onClick={() => setEditingId(null)}>✕</Button></div> : <Button size="sm" variant="outline" className="h-7 text-xs w-full" onClick={() => startEdit(p)}>{t("cost.edit_cost")}</Button>}
                </div>
              );
            })}
            {provs.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">{t("cost.no_data")}</div>}
          </div>
          {/* desktop table */}
          <div className="hidden md:block w-full overflow-x-auto"><table className="w-full text-sm"><thead className="border-b bg-muted/30 text-[11px] text-muted-foreground"><tr><th className="text-left px-5 py-2.5 font-medium">Provider</th><th className="text-right px-4 py-2.5 font-medium">Cost / gen</th><th className="text-right px-4 py-2.5 font-medium">Gens</th><th className="text-right px-4 py-2.5 font-medium">Success</th><th className="text-right px-4 py-2.5 font-medium">Total Cost</th><th className="text-left px-5 py-2.5 font-medium">Aksi</th></tr></thead><tbody className="divide-y">{provs.map(p => {
            const maxCost = Math.max(...provs.map(x => x.total_cost), 1); const w = Math.max(4, (p.total_cost / maxCost) * 100);
            const isMost = p.id === mostExpId, isCheap = p.id === cheapId;
            return <tr key={p.id} className={`hover:bg-muted/50 ${isMost ? "bg-red-50/30 dark:bg-red-950/10" : isCheap ? "bg-emerald-50/30 dark:bg-emerald-950/10" : ""}`}><td className="px-5 py-3"><div className="font-medium flex items-center gap-1.5"><Server className="h-3.5 w-3.5 text-muted-foreground" />{p.name}{isMost && <Badge variant="destructive" className="text-[9px] px-1">EXP</Badge>}{isCheap && <Badge variant="outline" className="text-[9px] px-1">CHEAP</Badge>}</div><div className="text-[11px] text-muted-foreground">{p.id} · {p.success_rate}% ok { !p.is_active && "· off"}</div><div className="mt-2 h-1.5 w-full rounded-full bg-muted overflow-hidden"><div className="h-full bg-primary rounded-full" style={{ width: `${w}%` }} /></div></td><td className="text-right px-4 py-3 font-mono text-xs">{editingId === p.id ? <Input className="h-7 w-24 text-xs ml-auto" value={editingCost} onChange={e => setEditingCost(e.target.value)} type="number" min={0} max={100000} step={0.0001} /> : <span className={isMost ? "text-red-600 font-bold" : isCheap ? "text-emerald-600 font-bold" : ""}>{fmtNum(p.cost_per_gen, 4)}</span>}</td><td className="text-right px-4 py-3 font-mono text-xs">{fmtNum(p.gen_count, 0)}</td><td className="text-right px-4 py-3 text-xs"><span className="text-emerald-600">{p.success}</span>/<span className="text-red-500">{p.failed}</span> <span className="text-muted-foreground">({p.success_rate}%)</span></td><td className="text-right px-4 py-3 font-mono text-xs font-semibold">{fmtMoney(p.total_cost)}</td><td className="px-5 py-3">{editingId === p.id ? <div className="flex gap-1"><Button size="sm" className="h-6 text-[11px]" onClick={() => saveEdit(p.id)} disabled={savingEdit}><Save className="h-3 w-3" />{t("cost.save")}</Button><Button size="sm" variant="ghost" className="h-6 text-[11px]" onClick={() => setEditingId(null)}>✕</Button></div> : <Button size="sm" variant="outline" className="h-6 text-[11px]" onClick={() => startEdit(p)}>{t("cost.edit_cost")}</Button>}</td></tr>; })}{provs.length === 0 && <tr><td colSpan={6} className="py-10 text-center text-sm text-muted-foreground">{t("cost.no_data")}</td></tr>}</tbody></table></div>
        </CardContent>
      </Card>

      <Card className="w-full overflow-hidden">
        <CardHeader><CardTitle><Bot className="h-4 w-4" />{t("cost.model_breakdown")} <Badge variant="secondary" className="ml-2 text-[11px]">{models.length}</Badge></CardTitle></CardHeader>
        <CardContent className="p-0">
          {models.length === 0 ? <div className="p-5 text-sm text-muted-foreground">{lang === "id" ? "Belum ada tracking per-model karena generations.model_id kosong — bot akan isi setelah update failover migration." : "No per-model tracking yet — generations.model_id empty."}</div> : (
            <div className="w-full overflow-x-auto"><table className="w-full text-sm min-w-[500px]"><thead className="border-b bg-muted/30 text-[11px] text-muted-foreground"><tr><th className="text-left px-5 py-2.5 font-medium">Model</th><th className="text-left px-4 py-2.5 font-medium">Provider</th><th className="text-right px-4 py-2.5 font-medium">Gens</th><th className="text-right px-4 py-2.5 font-medium">Rate</th><th className="text-right px-5 py-2.5 font-medium">Total</th></tr></thead><tbody className="divide-y">{models.map(m => { const maxG = Math.max(...models.map(x => x.gen_count), 1); const w = Math.max(4, (m.gen_count / maxG) * 100); return <tr key={m.model_id} className="hover:bg-muted/50"><td className="px-5 py-3"><div className="font-medium flex items-center gap-1.5"><Layers className="h-3.5 w-3.5 text-muted-foreground" />{m.display_name || m.model_id}</div><div className="text-[11px] text-muted-foreground truncate max-w-[180px]">{m.model_id}</div><div className="mt-1.5 h-1 w-full bg-muted rounded overflow-hidden"><div className="h-full bg-violet-500 rounded" style={{ width: `${w}%` }} /></div></td><td className="px-4 py-3 text-xs">{m.provider_id}</td><td className="px-4 py-3 text-right font-mono text-xs">{fmtNum(m.gen_count, 0)}</td><td className="px-4 py-3 text-right text-xs"><span className={m.success_rate > 90 ? "text-emerald-600" : m.success_rate > 70 ? "text-amber-600" : "text-red-600"}>{m.success_rate}%</span></td><td className="px-5 py-3 text-right font-mono text-xs">{fmtMoney(m.total_cost)}</td></tr>; })}</tbody></table></div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
