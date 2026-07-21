"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { Server, Zap, Clock, DollarSign, ArrowUp, ArrowDown, RefreshCw, Save, GripVertical, Activity, CheckCircle2, XCircle, Timer, Layers, Settings2, Power, Route } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Badge, Switch } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";
import { toast } from "sonner";
import { PageLoader } from "@/components/ui/page-loader";

type Provider = {
  id: string;
  name: string;
  base_url: string;
  is_active: boolean;
  failover_priority: number;
  timeout_sec: number;
  retry_count: number;
  cost_per_gen: number;
  models_total: number;
  models_active: number;
  gen_7d: number;
  success_7d: number;
  failed_7d: number;
  success_rate_7d: number;
  created_at?: string;
  updated_at?: string;
};

type PingResult = {
  [pid: string]: {
    latency_ms: number | null;
    ok: boolean;
    status_code?: number | null;
    error?: string | null;
    testing?: boolean;
  };
};

type EditDraft = { timeout_sec: number; retry_count: number; cost_per_gen: number };

export default function FailoverPage() {
  const { t, lang } = useLang();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingOrder, setSavingOrder] = useState(false);
  const [stats, setStats] = useState<{ total: number; active: number; avg_cost: number; failover_enabled: boolean } | null>(null);
  const [pingMap, setPingMap] = useState<PingResult>({});
  const [editId, setEditId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft>({ timeout_sec: 30, retry_count: 2, cost_per_gen: 0 });
  const [savingCfg, setSavingCfg] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const dragOverId = useRef<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api("/api/providers/failover");
      const list: Provider[] = (res.providers || []).slice().sort((a: Provider, b: Provider) => (a.failover_priority ?? 0) - (b.failover_priority ?? 0));
      setProviders(list);
      setStats({ total: res.total ?? list.length, active: res.active ?? 0, avg_cost: res.avg_cost ?? 0, failover_enabled: !!res.failover_enabled });
    } catch (e: any) {
      toast.error(e?.message || "Gagal memuat");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function moveItem(id: string, dir: -1 | 1) {
    const idx = providers.findIndex((p) => p.id === id);
    if (idx < 0) return;
    const nxtIdx = idx + dir;
    if (nxtIdx < 0 || nxtIdx >= providers.length) return;
    const arr = [...providers];
    const [removed] = arr.splice(idx, 1);
    arr.splice(nxtIdx, 0, removed);
    setProviders(arr);
  }

  async function saveOrder() {
    setSavingOrder(true);
    try {
      const order = providers.map((p) => p.id);
      await api("/api/providers/failover/reorder", { method: "POST", body: JSON.stringify({ order }) });
      toast.success(t("failover.saved"));
      await load();
    } catch (e: any) {
      toast.error(e?.message || "Gagal simpan urutan");
    } finally {
      setSavingOrder(false);
    }
  }

  async function testPing(pid: string) {
    setPingMap((m) => ({ ...m, [pid]: { ...(m[pid] || { ok: false, latency_ms: null }), testing: true } }));
    try {
      const res = await api(`/api/providers/${pid}/test-ping`, { method: "POST" });
      setPingMap((m) => ({
        ...m,
        [pid]: { latency_ms: res.latency_ms ?? res.avg_latency_ms ?? null, ok: !!res.ok, status_code: res.status_code ?? null, error: res.error || null, testing: false },
      }));
      if (res.ok) {
        toast.success(t("failover.ping_ok", { ms: String(res.latency_ms ?? "-") }));
      } else {
        toast.error(t("failover.ping_fail", { err: res.error || `HTTP ${res.status_code || "?"}` }));
      }
    } catch (e: any) {
      setPingMap((m) => ({ ...m, [pid]: { latency_ms: null, ok: false, status_code: null, error: e?.message || "error", testing: false } }));
      toast.error(t("failover.ping_fail", { err: e?.message || "error" }));
    }
  }

  async function toggleActive(pid: string) {
    try {
      await api(`/api/providers/${pid}/toggle`, { method: "POST" });
      toast.success(`Provider ${pid} toggled`);
      await load();
    } catch (e: any) {
      toast.error(e?.message || "Gagal toggle");
    }
  }

  function openEdit(p: Provider) {
    setEditId(p.id);
    setEditDraft({ timeout_sec: p.timeout_sec ?? 30, retry_count: p.retry_count ?? 2, cost_per_gen: Number(p.cost_per_gen ?? 0) });
  }

  async function saveConfig(pid: string) {
    if (!editDraft) return;
    if (editDraft.timeout_sec < 5 || editDraft.timeout_sec > 120) { toast.error("timeout 5-120"); return; }
    if (editDraft.retry_count < 0 || editDraft.retry_count > 5) { toast.error("retry 0-5"); return; }
    if (editDraft.cost_per_gen < 0 || editDraft.cost_per_gen > 100000) { toast.error("cost 0-100000"); return; }
    setSavingCfg(pid);
    try {
      await api(`/api/providers/${pid}/failover-config`, {
        method: "PUT",
        body: JSON.stringify({
          timeout_sec: Number(editDraft.timeout_sec),
          retry_count: Number(editDraft.retry_count),
          cost_per_gen: Number(editDraft.cost_per_gen),
        }),
      });
      toast.success(t("failover.cfg_saved"));
      setEditId(null);
      await load();
    } catch (e: any) {
      toast.error(e?.message || "Gagal simpan config");
    } finally {
      setSavingCfg(null);
    }
  }

  // drag helpers html5
  function onDragStart(e: React.DragEvent, id: string) {
    setDragId(id);
    e.dataTransfer.effectAllowed = "move";
    // ghost opacity handled via CSS
  }
  function onDragOver(e: React.DragEvent, id: string) {
    e.preventDefault();
    dragOverId.current = id;
  }
  function onDrop(e: React.DragEvent, targetId: string) {
    e.preventDefault();
    if (!dragId || dragId === targetId) {
      setDragId(null);
      return;
    }
    const fromIdx = providers.findIndex((p) => p.id === dragId);
    const toIdx = providers.findIndex((p) => p.id === targetId);
    if (fromIdx < 0 || toIdx < 0) { setDragId(null); return; }
    const arr = [...providers];
    const [moved] = arr.splice(fromIdx, 1);
    arr.splice(toIdx, 0, moved);
    setProviders(arr);
    setDragId(null);
    dragOverId.current = null;
  }
  function onDragEnd() {
    setDragId(null);
    dragOverId.current = null;
  }

  if (loading) {
    return <PageLoader label={t("common.loading")} cards={2} rows={3} />;
  }

  return (
    <div className="flex flex-col gap-4 md:gap-6 p-1 w-full max-w-full min-w-0">
      <div className="space-y-1">
        <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2"><Route className="h-5 w-5 md:h-6 md:w-6 shrink-0" />{t("failover.title")}</h1>
        <p className="text-xs md:text-sm text-muted-foreground">{t("failover.sub")}</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card><CardHeader className="pb-1"><CardTitle className="text-xs"><Server className="h-4 w-4" />{t("failover.total")}</CardTitle></CardHeader><CardContent><div className="text-2xl font-extrabold">{stats?.total ?? providers.length}</div><div className="text-[11px] text-muted-foreground mt-1">{(providers.length || 0)} {lang === "id" ? "koneksi provider" : "provider connections"}</div></CardContent></Card>
        <Card><CardHeader className="pb-1"><CardTitle className="text-xs"><Power className="h-4 w-4" />{t("failover.active")}</CardTitle></CardHeader><CardContent><div className="text-2xl font-extrabold text-emerald-600">{stats?.active ?? 0}</div><div className="text-[11px] text-muted-foreground mt-1">{lang === "id" ? "aktif untuk fallback" : "active for fallback"}</div></CardContent></Card>
        <Card><CardHeader className="pb-1"><CardTitle className="text-xs"><DollarSign className="h-4 w-4" />{t("failover.avg_cost")}</CardTitle></CardHeader><CardContent><div className="text-2xl font-extrabold">{stats?.avg_cost?.toFixed ? stats.avg_cost.toFixed(4) : stats?.avg_cost ?? 0}</div><div className="text-[11px] text-muted-foreground mt-1">per gen avg</div></CardContent></Card>
        <Card className={stats?.failover_enabled ? "border-emerald-500/30" : "border-amber-500/30"}><CardHeader className="pb-1"><CardTitle className="text-xs"><Zap className="h-4 w-4" />{t("failover.enabled")}</CardTitle></CardHeader><CardContent><div className={`text-sm font-bold flex items-center gap-1 ${stats?.failover_enabled ? "text-emerald-600" : "text-amber-600"}`}>{stats?.failover_enabled ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{stats?.failover_enabled ? t("failover.enabled_yes") : t("failover.enabled_no")}</div><div className="text-[11px] text-muted-foreground mt-1">{lang === "id" ? "butuh >1 aktif" : "needs >1 active"}</div></CardContent></Card>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4" />{t("failover.refresh")}</Button>
        <Button size="sm" onClick={saveOrder} disabled={savingOrder || providers.length === 0}><Save className="h-4 w-4" />{savingOrder ? t("failover.saving") : t("failover.save_order")}</Button>
      </div>

      <Card className="overflow-hidden">
        <CardHeader className="pb-2"><CardTitle className="text-sm"><Layers className="h-4 w-4" />{t("failover.list")} <Badge variant="muted" className="ml-2 text-[10px]">{providers.length} items · drag + {lang === "id" ? "panah naik/turun" : "up/down arrows"}</Badge></CardTitle></CardHeader>
        <CardContent className="px-0 pt-0">
          {providers.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground">{t("failover.no_providers")}</div>}
          <div className="flex flex-col divide-y">
            {providers.map((p, idx) => {
              const ping = pingMap[p.id];
              const isDragging = dragId === p.id;
              const isEdit = editId === p.id;
              return (
                <div
                  key={p.id}
                  draggable={!isEdit}
                  onDragStart={(e) => onDragStart(e, p.id)}
                  onDragOver={(e) => onDragOver(e, p.id)}
                  onDrop={(e) => onDrop(e, p.id)}
                  onDragEnd={onDragEnd}
                  className={`group flex flex-col gap-2 px-3 md:px-4 py-3 hover:bg-accent/50 transition-colors ${isDragging ? "opacity-50" : ""} ${dragOverId.current === p.id ? "bg-accent" : ""}`}
                >
                  {/* Desktop / main row */}
                  <div className="flex items-start gap-2 md:gap-3 w-full">
                    <div className="hidden md:flex items-center gap-1.5 pt-1">
                      <span className="cursor-grab select-none text-muted-foreground group-hover:text-foreground" title="drag">
                        <GripVertical className="h-4 w-4" />
                      </span>
                      <span className="text-xs font-mono w-6 text-center font-bold">{idx}</span>
                    </div>
                    <div className="flex md:hidden flex-col items-center gap-1 pt-0.5">
                      <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => moveItem(p.id, -1)} disabled={idx === 0}><ArrowUp className="h-3 w-3" /></Button>
                      <span className="text-[11px] font-mono font-bold">{idx}</span>
                      <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => moveItem(p.id, 1)} disabled={idx === providers.length - 1}><ArrowDown className="h-3 w-3" /></Button>
                    </div>

                    <div className="flex-1 min-w-0 flex flex-col gap-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-sm flex items-center gap-1.5">
                          <Server className="h-3.5 w-3.5" /> {p.id}
                          <Badge variant={p.is_active ? "success" : "destructive"} className="text-[10px]">{p.is_active ? (lang === "id" ? "aktif" : "active") : "off"}</Badge>
                          {p.failover_priority === 0 && <Badge variant="muted" className="text-[10px]">primary</Badge>}
                        </span>
                        <span className="text-[11px] text-muted-foreground truncate max-w-[200px] md:max-w-[260px]">{p.base_url}</span>
                      </div>

                      {!isEdit ? (
                        <div className="flex flex-wrap gap-1.5 text-[11px]">
                          <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5"><Clock className="h-3 w-3" />{p.timeout_sec}s</span>
                          <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5"><Activity className="h-3 w-3" />retry {p.retry_count}</span>
                          <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5"><DollarSign className="h-3 w-3" />{Number(p.cost_per_gen || 0).toFixed(4)}</span>
                          <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5"><Layers className="h-3 w-3" />{p.models_active}/{p.models_total} models</span>
                          <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5"><Zap className="h-3 w-3" />{p.gen_7d} gen 7d</span>
                          <span className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-emerald-600 border-emerald-200"><CheckCircle2 className="h-3 w-3" />{p.success_rate_7d}% ok</span>
                          {ping && (
                            <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 border text-[11px] ${ping.ok ? "border-emerald-200 text-emerald-600 bg-emerald-50/50 dark:bg-emerald-900/20" : "border-red-200 text-red-600 bg-red-50/50 dark:bg-red-900/20"}`}>
                              <Timer className="h-3 w-3" />{ping.latency_ms != null ? `${ping.latency_ms}ms` : (ping.error || "fail")} {ping.status_code ? `· ${ping.status_code}` : ""}
                            </span>
                          )}
                        </div>
                      ) : (
                        <div className="flex flex-col md:flex-row gap-2 pt-1">
                          <div className="flex flex-wrap gap-2 flex-1">
                            <div className="flex flex-col gap-0.5">
                              <label className="text-[10px] text-muted-foreground">{t("failover.timeout")}</label>
                              <Input type="number" min={5} max={120} className="h-8 w-[110px] text-xs" value={editDraft.timeout_sec} onChange={(e) => setEditDraft((d) => ({ ...d, timeout_sec: Math.max(5, Math.min(120, Number(e.target.value) || 5)) }))} />
                            </div>
                            <div className="flex flex-col gap-0.5">
                              <label className="text-[10px] text-muted-foreground">{t("failover.retry")}</label>
                              <Input type="number" min={0} max={5} className="h-8 w-[90px] text-xs" value={editDraft.retry_count} onChange={(e) => setEditDraft((d) => ({ ...d, retry_count: Math.max(0, Math.min(5, Number(e.target.value) || 0)) }))} />
                            </div>
                            <div className="flex flex-col gap-0.5">
                              <label className="text-[10px] text-muted-foreground">{t("failover.cost")}</label>
                              <Input type="number" min={0} max={100000} step={0.0001} className="h-8 w-[120px] text-xs" value={editDraft.cost_per_gen} onChange={(e) => setEditDraft((d) => ({ ...d, cost_per_gen: Math.max(0, Math.min(100000, Number(e.target.value) || 0)) }))} />
                            </div>
                          </div>
                          <div className="flex gap-1.5 items-end">
                            <Button size="sm" onClick={() => saveConfig(p.id)} disabled={savingCfg === p.id}><Save className="h-3.5 w-3.5" />{savingCfg === p.id ? t("failover.saving") : t("failover.save_cfg")}</Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>{t("common.cancel")}</Button>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex flex-col md:flex-row gap-1.5 shrink-0">
                      {!isEdit ? (
                        <>
                          <div className="hidden md:flex gap-1">
                            <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => moveItem(p.id, -1)} disabled={idx === 0} title="move up"><ArrowUp className="h-3.5 w-3.5" /></Button>
                            <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => moveItem(p.id, 1)} disabled={idx === providers.length - 1} title="move down"><ArrowDown className="h-3.5 w-3.5" /></Button>
                          </div>
                          <Button size="sm" variant="outline" className="h-7 text-[11px]" onClick={() => openEdit(p)}><Settings2 className="h-3.5 w-3.5" />{lang === "id" ? "Edit" : "Edit"}</Button>
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-w-[86px]" onClick={() => testPing(p.id)} disabled={!!ping?.testing}>
                            {ping?.testing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
                            {ping?.testing ? t("failover.testing") : t("failover.test")}
                          </Button>
                          <Switch checked={!!p.is_active} onChange={() => toggleActive(p.id)} />
                        </>
                      ) : null}
                      {/* mobile: duplicate up/down already handled */}
                      <div className="md:hidden flex gap-1">
                        {!isEdit && <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => toggleActive(p.id)} title="toggle active"><Power className={`h-3.5 w-3.5 ${p.is_active ? "text-emerald-600" : "text-muted-foreground"}`} /></Button>}
                      </div>
                    </div>
                  </div>

                  {/* mobile card extra row for latency detail */}
                  {ping && (
                    <div className="md:hidden text-[10px] text-muted-foreground pl-8">
                      {t("failover.latency")}: {ping.latency_ms != null ? `${ping.latency_ms}ms` : "—"} {ping.ok ? "ok" : ping.error ? `· ${ping.error}` : ""}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-xs"><Settings2 className="h-4 w-4" />{t("failover.how_title")}</CardTitle></CardHeader>
        <CardContent className="text-xs text-muted-foreground space-y-1">
          <div>1. {t("failover.how1")}</div>
          <div>2. {t("failover.how2")}</div>
          <div>3. {t("failover.how3")}</div>
          <div>4. {t("failover.how4")}</div>
        </CardContent>
      </Card>
    </div>
  );
}
