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

type Daily = {
  date: string;
  day: string;
  gen_count: number;
  success: number;
  failed: number;
  revenue: number;
  cost: number;
  profit: number;
};

type ProviderBreakdown = {
  id: string;
  name: string;
  is_active: boolean;
  cost_per_gen: number;
  gen_count: number;
  success: number;
  failed: number;
  success_rate: number;
  total_cost: number;
};

type ModelBreakdown = {
  model_id: string;
  display_name: string;
  provider_id: string;
  cost_per_gen: number;
  gen_count: number;
  success: number;
  failed: number;
  success_rate: number;
  total_cost: number;
};

type CostStats = {
  period: string;
  days: number;
  totals: {
    total_cost: number;
    total_revenue: number;
    total_profit: number;
    total_gens: number;
    total_success: number;
    total_failed: number;
    avg_cost_per_gen: number;
    deposit_revenue: number;
    order_revenue: number;
    most_expensive_provider: { id: string; name: string; cost_per_gen: number } | null;
    cheapest_provider: { id: string; name: string; cost_per_gen: number } | null;
    highest_usage_provider: { id: string; name: string; gen_count: number } | null;
  };
  daily: Daily[];
  provider_breakdown: ProviderBreakdown[];
  model_breakdown: ModelBreakdown[];
};

const PERIOD_OPTS = [
  { value: "7d", label: "7 hari / 7 days" },
  { value: "30d", label: "30 hari / 30 days" },
  { value: "90d", label: "90 hari / 90 days" },
  { value: "365d", label: "365 hari / 365 days" },
];

function fmtMoney(n: number): string {
  if (Math.abs(n) >= 1_000_000) return "Rp " + (n / 1_000_000).toFixed(2) + "M";
  if (Math.abs(n) >= 1_000) return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
  return "Rp " + n.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtNumber(n: number | null | undefined, decimals = 2): string {
  if (n == null || isNaN(n)) return "0";
  if (decimals === 0) return Math.round(n).toLocaleString("id-ID");
  return n.toLocaleString("id-ID", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function MiniBarChart({ data, maxKey }: { data: Daily[]; maxKey: keyof Daily }) {
  const maxVal = useMemo(() => {
    let mx = 1;
    for (const d of data) {
      const v = Number(d[maxKey] as any) || 0;
      const rv = Number(d.revenue) || 0;
      const cv = Number(d.cost) || 0;
      mx = Math.max(mx, v, rv, cv, Math.abs(Number(d.profit) || 0));
    }
    return mx;
  }, [data, maxKey]);

  if (!data.length) return <div className="py-10 text-center text-xs text-muted-foreground">No data</div>;

  // For mobile horizontal scroll container
  return (
    <div className="w-full overflow-x-auto scrollbar-thin">
      <div className="min-w-[520px] flex flex-col gap-1">
        {/* Legend */}
        <div className="flex gap-3 text-[10px] text-muted-foreground mb-1 px-1">
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-emerald-500" /> Revenue</span>
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-amber-500" /> Cost</span>
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-violet-500" /> Profit</span>
          <span className="inline-flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-slate-400" /> Gens</span>
        </div>
        {/* Bars */}
        <div className="flex items-end gap-[3px] h-[140px] md:h-[160px] border-b border-l px-1 pb-1">
          {data.map((d, i) => {
            const revH = Math.max(2, Math.round(((d.revenue || 0) / maxVal) * 120));
            const costH = Math.max(2, Math.round(((d.cost || 0) / maxVal) * 120));
            // profit can be negative — handle separate up/down zero line centered?
            // Simplify: profit bar green up if positive, red down fixed height proportion
            const profAbs = Math.abs(d.profit || 0);
            const profH = Math.max(2, Math.round((profAbs / maxVal) * 100));
            const isProfPos = (d.profit || 0) >= 0;
            const genH = Math.max(2, Math.round(((Number(d[maxKey]) || 0) / Math.max(maxVal, 1)) * 30));
            // Only meaningful if maxKey is gen_count — but we still show revenue/cost as main
            return (
              <div key={i} className="flex flex-1 flex-col items-center justify-end gap-[2px] min-w-0">
                <div className="flex items-end gap-[2px] w-full justify-center">
                  {/* revenue bar */}
                  <div
                    className="w-[4px] md:w-[6px] rounded-t bg-emerald-500/80 hover:bg-emerald-500 transition-colors"
                    style={{ height: revH + "px" }}
                    title={`${d.date} revenue ${fmtMoney(d.revenue)}`}
                  />
                  {/* cost bar */}
                  <div
                    className="w-[4px] md:w-[6px] rounded-t bg-amber-500/80 hover:bg-amber-500 transition-colors"
                    style={{ height: costH + "px" }}
                    title={`${d.date} cost ${fmtMoney(d.cost)}`}
                  />
                  {/* profit indicator dot/bar */}
                  <div
                    className={`w-[4px] md:w-[6px] rounded-t ${isProfPos ? "bg-violet-500/80" : "bg-red-500/80"}`}
                    style={{ height: profH + "px" }}
                    title={`${d.date} profit ${fmtMoney(d.profit)} ${isProfPos ? "(+)" : "(-)"}`}
                  />
                </div>
                <span className="text-[8px] md:text-[9px] text-muted-foreground mt-1 truncate w-full text-center">{d.day}</span>
              </div>
            );
          })}
        </div>
        {/* X labels for gens overlay small line */}
        <div className="flex gap-[3px] px-1">
          {data.map((d, i) => {
            const gh = Math.max(1, Math.round(((d.gen_count || 0) / Math.max(...data.map(x => x.gen_count || 1), 1)) * 18));
            return (
              <div key={i} className="flex-1 flex justify-center">
                <div className="w-[4px] md:w-[6px] rounded bg-slate-400/60" style={{ height: gh + "px" }} title={`${d.date} gen ${d.gen_count}`} />
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
  const [period, setPeriod] = useState<string>("30d");
  const [stats, setStats] = useState<CostStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  // inline edit cost_per_gen
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingCost, setEditingCost] = useState<string>("");
  const [savingEdit, setSavingEdit] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = (await api(`/api/cost/stats?period=${period}`)) as CostStats;
      setStats(res);
    } catch (e: any) {
      setErr(e?.message || "Gagal memuat cost stats");
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  const startEdit = (p: ProviderBreakdown) => {
    setEditingId(p.id);
    setEditingCost(String(p.cost_per_gen ?? 0));
  };
  const cancelEdit = () => { setEditingId(null); setEditingCost(""); };

  const saveEdit = async (pid: string) => {
    const v = parseFloat(editingCost);
    if (isNaN(v) || v < 0 || v > 100000) {
      toast.error("cost 0-100000");
      return;
    }
    setSavingEdit(true);
    try {
      await api(`/api/cost/providers/${pid}`, { method: "PUT", body: JSON.stringify({ cost_per_gen: v }) });
      toast.success(lang === "id" ? "Biaya disimpan" : "Cost saved");
      setEditingId(null);
      await load();
    } catch (e: any) {
      toast.error(e?.message || "Gagal simpan");
    } finally {
      setSavingEdit(false);
    }
  };

  if (loading && !stats) {
    return (
      <div className="flex flex-col gap-4 w-full">
        <div className="flex items-center gap-2 text-sm text-muted-foreground"><RefreshCw className="h-4 w-4 animate-spin" />{t("common.loading")}</div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 rounded-lg border bg-card animate-pulse" />)}
        </div>
      </div>
    );
  }
  if (err) {
    return <div className="py-20 text-center text-sm"><div className="text-destructive">{err}</div><Button size="sm" variant="outline" className="mt-3" onClick={load}><RefreshCw className="h-4 w-4" />Retry</Button></div>;
  }
  if (!stats) return null;

  const totals = stats.totals;
  const daily = stats.daily || [];
  const provs = stats.provider_breakdown || [];
  const models = stats.model_breakdown || [];
  const maxGen = Math.max(...daily.map(d => d.gen_count), 1);
  const totalRevenue = totals.total_revenue || 0;
  const totalCost = totals.total_cost || 0;
  const totalProfit = totals.total_profit || 0;
  const isProfitPos = totalProfit >= 0;
  const avgCost = totals.avg_cost_per_gen || 0;

  // Highlight ids for cheapest/most expensive
  const mostExpId = totals.most_expensive_provider?.id;
  const cheapestId = totals.cheapest_provider?.id;
  const highestUsageId = totals.highest_usage_provider?.id;

  return (
    <div className="flex flex-col gap-4 md:gap-5 w-full max-w-full overflow-hidden pb-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2"><DollarSign className="h-5 w-5 md:h-6 md:w-6 shrink-0" />{t("cost.title")}</h1>
          <p className="text-xs md:text-sm text-muted-foreground mt-1">{t("cost.sub")}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex flex-col gap-0.5">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{t("cost.period")}</span>
            <CustomSelect value={period} onChange={setPeriod} options={PERIOD_OPTS} className="w-[170px]" />
          </div>
          <Button variant="outline" size="sm" onClick={load} disabled={loading} className="h-9 mt-4"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />{t("cost.refresh")}</Button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="border-l-4 border-l-amber-500">
          <CardHeader className="pb-1"><CardTitle className="text-[11px]"><Banknote className="h-4 w-4" />{t("cost.total_cost")} · {stats.days}d</CardTitle></CardHeader>
          <CardContent className="pt-1">
            <div className="text-lg md:text-xl font-extrabold">{fmtMoney(totalCost)}</div>
            <div className="text-[11px] text-muted-foreground mt-1">{fmtNumber(totals.total_gens, 0)} gens · {t("cost.avg_cost_gen")} {fmtNumber(avgCost, 4)}</div>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-emerald-500">
          <CardHeader className="pb-1"><CardTitle className="text-[11px]"><Wallet className="h-4 w-4" />{t("cost.total_revenue")}</CardTitle></CardHeader>
          <CardContent className="pt-1">
            <div className="text-lg md:text-xl font-extrabold text-emerald-600 dark:text-emerald-400">{fmtMoney(totalRevenue)}</div>
            <div className="text-[11px] text-muted-foreground mt-1">{t("cost.deposit_rev")} {fmtMoney(totals.deposit_revenue)} · {t("cost.order_rev")} {fmtMoney(totals.order_revenue)}</div>
          </CardContent>
        </Card>
        <Card className={`border-l-4 ${isProfitPos ? "border-l-violet-500" : "border-l-red-500"}`}>
          <CardHeader className="pb-1"><CardTitle className="text-[11px]">{isProfitPos ? <TrendingUp className="h-4 w-4 text-violet-600" /> : <TrendingDown className="h-4 w-4 text-red-600" />}{t("cost.profit")} {isProfitPos ? <span className="text-emerald-600">{t("cost.profit_positive")}</span> : <span className="text-red-600">{t("cost.profit_negative")}</span>}</CardTitle></CardHeader>
          <CardContent className="pt-1">
            <div className={`text-lg md:text-xl font-extrabold ${isProfitPos ? "text-violet-600 dark:text-violet-400" : "text-red-600"}`}>{isProfitPos ? "+" : ""}{fmtMoney(totalProfit)}</div>
            <div className="text-[11px] text-muted-foreground mt-1">margin {totalRevenue > 0 ? ((totalProfit / totalRevenue) * 100).toFixed(1) : "0"}% · {fmtNumber(totals.total_gens, 0)} gens</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-1"><CardTitle className="text-[11px]"><BarChart3 className="h-4 w-4" />{t("cost.total_gens")} · Success</CardTitle></CardHeader>
          <CardContent className="pt-1">
            <div className="text-lg md:text-xl font-extrabold">{fmtNumber(totals.total_gens, 0)}</div>
            <div className="text-[11px] text-muted-foreground mt-1 flex gap-2"><span className="text-emerald-600">{fmtNumber(totals.total_success, 0)} ok</span> <span className="text-red-500">{fmtNumber(totals.total_failed, 0)} fail</span> · rate {totals.total_gens > 0 ? ((totals.total_success / totals.total_gens) * 100).toFixed(1) : "0"}%</div>
          </CardContent>
        </Card>
      </div>

      {/* Secondary quick highlights */}
      <div className="flex flex-wrap gap-2 text-[11px]">
        {totals.most_expensive_provider && <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 dark:bg-red-900/20 px-2.5 py-1 text-red-700 dark:text-red-300"><DollarSign className="h-3 w-3" />{t("cost.most_exp")}: {totals.most_expensive_provider.name} · {fmtNumber(totals.most_expensive_provider.cost_per_gen, 4)}</span>}
        {totals.cheapest_provider && <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 dark:bg-emerald-900/20 px-2.5 py-1 text-emerald-700 dark:text-emerald-300"><CheckCircle2 className="h-3 w-3" />{t("cost.cheapest")}: {totals.cheapest_provider.name} · {fmtNumber(totals.cheapest_provider.cost_per_gen, 4)}</span>}
        {totals.highest_usage_provider && <span className="inline-flex items-center gap-1 rounded-full border bg-muted px-2.5 py-1"><Zap className="h-3 w-3" />{t("cost.highest_usage")}: {totals.highest_usage_provider.name} · {fmtNumber(totals.highest_usage_provider.gen_count, 0)} gens</span>}
      </div>

      {/* Daily chart */}
      <Card className="overflow-hidden">
        <CardHeader className="pb-2"><CardTitle className="text-sm"><Activity className="h-4 w-4" />{t("cost.daily_chart")} <Badge variant="muted" className="ml-2 text-[10px]">{daily.length}d · {stats.period}</Badge></CardTitle></CardHeader>
        <CardContent>
          {daily.length === 0 ? <div className="py-12 text-center text-sm text-muted-foreground">{t("cost.no_data")}</div> : (
            <>
              <MiniBarChart data={daily} maxKey="gen_count" />
              {/* Table fallback minimal */}
              <div className="mt-4 max-h-[240px] overflow-auto border rounded-lg">
                <table className="w-full text-[11px] md:text-xs">
                  <thead className="sticky top-0 bg-card border-b text-muted-foreground">
                    <tr><th className="text-left px-2 py-1.5 font-semibold">Date</th><th className="text-right px-2 py-1.5">Gens</th><th className="text-right px-2 py-1.5">Rev</th><th className="text-right px-2 py-1.5">Cost</th><th className="text-right px-2 py-1.5">Profit</th><th className="text-right px-2 py-1.5">Ok/Fail</th></tr>
                  </thead>
                  <tbody className="divide-y">
                    {daily.slice().reverse().slice(0, 30).map(d => (
                      <tr key={d.date} className="hover:bg-muted/50">
                        <td className="px-2 py-1">{d.date} <span className="text-muted-foreground">{d.day}</span></td>
                        <td className="text-right px-2 py-1 font-mono">{fmtNumber(d.gen_count, 0)}</td>
                        <td className="text-right px-2 py-1 font-mono text-emerald-600">{fmtMoney(d.revenue)}</td>
                        <td className="text-right px-2 py-1 font-mono text-amber-600">{fmtMoney(d.cost)}</td>
                        <td className={`text-right px-2 py-1 font-mono font-semibold ${d.profit >= 0 ? "text-violet-600" : "text-red-600"}`}>{fmtMoney(d.profit)}</td>
                        <td className="text-right px-2 py-1 text-[10px]"><span className="text-emerald-600">{d.success}</span>/<span className="text-red-500">{d.failed}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Provider breakdown */}
      <Card className="overflow-hidden">
        <CardHeader className="pb-2"><CardTitle className="text-sm"><Server className="h-4 w-4" />{t("cost.provider_breakdown")} <Badge variant="muted" className="ml-2 text-[10px]">{provs.length} providers</Badge></CardTitle></CardHeader>
        <CardContent className="px-0 pt-0">
          <div className="w-full overflow-x-auto">
            <table className="w-full text-xs md:text-sm">
              <thead className="border-b bg-muted/30 text-[11px] text-muted-foreground">
                <tr><th className="text-left px-3 py-2">Provider</th><th className="text-right px-3 py-2">Cost /gen</th><th className="text-right px-3 py-2">Gens</th><th className="text-right px-3 py-2">Success</th><th className="text-right px-3 py-2">Total Cost</th><th className="text-left px-3 py-2">Aksi</th></tr>
              </thead>
              <tbody className="divide-y">
                {provs.map(p => {
                  const isMost = p.id === mostExpId;
                  const isCheap = p.id === cheapestId;
                  const isTop = p.id === highestUsageId;
                  const maxCostInList = Math.max(...provs.map(x => x.total_cost), 1);
                  const widthPct = Math.max(4, (p.total_cost / maxCostInList) * 100);
                  return (
                    <tr key={p.id} className={`hover:bg-muted/50 ${isMost ? "bg-red-50/50 dark:bg-red-950/20" : isCheap ? "bg-emerald-50/60 dark:bg-emerald-950/20" : ""}`}>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5 font-semibold"><Server className="h-3.5 w-3.5 text-muted-foreground" />{p.name}
                          {isMost && <Badge variant="destructive" className="text-[8px] px-1">EXP</Badge>}
                          {isCheap && <Badge variant="success" className="text-[8px] px-1">CHEAP</Badge>}
                          {isTop && <Badge variant="default" className="text-[8px] px-1">TOP</Badge>}
                          {!p.is_active && <Badge variant="muted" className="text-[8px]">off</Badge>}
                        </div>
                        <div className="text-[10px] text-muted-foreground">{p.id} · {p.success_rate}% ok</div>
                        <div className="mt-1 h-1.5 w-full rounded-full bg-muted overflow-hidden"><div className="h-full bg-amber-500 rounded-full" style={{ width: `${widthPct}%` }} /></div>
                      </td>
                      <td className="text-right px-3 py-2.5 font-mono text-[11px] md:text-xs">
                        {editingId === p.id ? (
                          <div className="flex items-center gap-1 justify-end">
                            <Input className="h-7 w-24 text-xs" value={editingCost} onChange={e => setEditingCost(e.target.value)} type="number" min={0} max={100000} step={0.0001} />
                          </div>
                        ) : <span className={isMost ? "text-red-600 font-bold" : isCheap ? "text-emerald-600 font-bold" : ""}>{fmtNumber(p.cost_per_gen, 4)}</span>}
                      </td>
                      <td className="text-right px-3 py-2.5 font-mono">{fmtNumber(p.gen_count, 0)}</td>
                      <td className="text-right px-3 py-2.5 text-[11px]"><span className="text-emerald-600">{p.success}</span>/<span className="text-red-500">{p.failed}</span> <span className="text-muted-foreground">({p.success_rate}%)</span></td>
                      <td className="text-right px-3 py-2.5 font-mono font-semibold">{fmtMoney(p.total_cost)}</td>
                      <td className="px-3 py-2.5">
                        {editingId === p.id ? (
                          <div className="flex gap-1">
                            <Button size="sm" className="h-6 text-[11px]" onClick={() => saveEdit(p.id)} disabled={savingEdit}><Save className="h-3 w-3" />{t("cost.save")}</Button>
                            <Button size="sm" variant="ghost" className="h-6 text-[11px]" onClick={cancelEdit}>✕</Button>
                          </div>
                        ) : <Button size="sm" variant="outline" className="h-6 text-[11px]" onClick={() => startEdit(p)}>{t("cost.edit_cost")}</Button>}
                      </td>
                    </tr>
                  );
                })}
                {provs.length === 0 && <tr><td colSpan={6} className="text-center py-10 text-muted-foreground text-sm">{t("cost.no_data")}</td></tr>}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Model breakdown */}
      <Card className="overflow-hidden">
        <CardHeader className="pb-2"><CardTitle className="text-sm"><Bot className="h-4 w-4" />{t("cost.model_breakdown")} <Badge variant="muted" className="ml-2 text-[10px]">{models.length} models tracked</Badge></CardTitle></CardHeader>
        <CardContent className="px-0 pt-0">
          {models.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground px-4">
              {lang === "id" ? "Belum ada tracking per-model karena generations.model_id kosong — bot mulai isi setelah update failover migration. Provider breakdown menampilkan estimasi." : "No per-model tracking yet because generations.model_id empty — bot will fill after failover migration. Provider breakdown shows estimate."}
            </div>
          ) : (
            <div className="w-full overflow-x-auto">
              <table className="w-full text-xs md:text-sm">
                <thead className="border-b bg-muted/30 text-[11px] text-muted-foreground">
                  <tr><th className="text-left px-3 py-2">Model</th><th className="text-left px-3 py-2">Provider</th><th className="text-right px-3 py-2">Gens</th><th className="text-right px-3 py-2">Rate</th><th className="text-right px-3 py-2">Cost Total</th></tr>
                </thead>
                <tbody className="divide-y">
                  {models.map(m => {
                    const maxG = Math.max(...models.map(x => x.gen_count), 1);
                    const w = Math.max(4, (m.gen_count / maxG) * 100);
                    return (
                      <tr key={m.model_id} className="hover:bg-muted/50">
                        <td className="px-3 py-2.5">
                          <div className="font-medium flex items-center gap-1"><Layers className="h-3 w-3 text-muted-foreground" />{m.display_name || m.model_id}</div>
                          <div className="text-[10px] text-muted-foreground truncate max-w-[200px]">{m.model_id}</div>
                          <div className="mt-1 h-1 w-full bg-muted rounded overflow-hidden"><div className="h-full bg-violet-500 rounded" style={{ width: `${w}%` }} /></div>
                        </td>
                        <td className="px-3 py-2.5 text-[11px]">{m.provider_id}</td>
                        <td className="px-3 py-2.5 text-right font-mono">{fmtNumber(m.gen_count, 0)}</td>
                        <td className="px-3 py-2.5 text-right text-[11px]"><span className={m.success_rate > 90 ? "text-emerald-600" : m.success_rate > 70 ? "text-amber-600" : "text-red-600"}>{m.success_rate}%</span> <span className="text-muted-foreground">{m.success}/{m.failed}</span></td>
                        <td className="px-3 py-2.5 text-right font-mono">{fmtMoney(m.total_cost)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Revenue vs cost visual bar */}
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-xs"><Wallet className="h-4 w-4" />Revenue vs Cost split</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-[11px] text-muted-foreground mb-1">Revenue split</div>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
                <div className="h-full bg-emerald-500" style={{ width: `${totalRevenue > 0 ? (totals.deposit_revenue / totalRevenue) * 100 : 0}%` }} title={`Deposit ${fmtMoney(totals.deposit_revenue)}`} />
                <div className="h-full bg-blue-500" style={{ width: `${totalRevenue > 0 ? (totals.order_revenue / totalRevenue) * 100 : 0}%` }} title={`Orders ${fmtMoney(totals.order_revenue)}`} />
              </div>
              <div className="mt-1 flex justify-between text-[10px]"><span>Deposits {fmtMoney(totals.deposit_revenue)}</span><span>Orders {fmtMoney(totals.order_revenue)}</span></div>
            </div>
            <div>
              <div className="text-[11px] text-muted-foreground mb-1">Cost vs Margin</div>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
                <div className="h-full bg-amber-500" style={{ width: `${totalRevenue > 0 ? Math.min(100, (totalCost / totalRevenue) * 100) : 0}%` }} title={`Cost ${fmtMoney(totalCost)}`} />
                <div className="h-full bg-violet-500" style={{ width: `${totalRevenue > 0 ? Math.max(0, (totalProfit / totalRevenue) * 100) : 0}%` }} title={`Profit ${fmtMoney(totalProfit)}`} />
              </div>
              <div className="mt-1 flex justify-between text-[10px]"><span>Cost {fmtMoney(totalCost)}</span><span className={isProfitPos ? "text-violet-600" : "text-red-600"}>Profit {fmtMoney(totalProfit)}</span></div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-dashed">
        <CardHeader className="pb-2"><CardTitle className="text-xs">ℹ️ {t("cost.how_title")}</CardTitle></CardHeader>
        <CardContent className="text-xs text-muted-foreground space-y-1">
          <div>1. {t("cost.how1")}</div>
          <div>2. {t("cost.how2")}</div>
          <div>3. {t("cost.how3")}</div>
          <div>4. {t("cost.how4")}</div>
        </CardContent>
      </Card>
    </div>
  );
}
