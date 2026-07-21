"use client";
import { useEffect, useState, useCallback } from "react";
import { Bell, Plus, Pencil, Trash2, Send, Power, RefreshCw, AlertTriangle, Siren, Webhook, Timer, Activity, Cpu, HardDrive, Clock, Layers, Bot, BarChart3, DollarSign, CheckCircle2, XCircle } from "lucide-react";
import { PageLoader } from "@/components/ui/page-loader";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Badge, Textarea } from "@/components/ui/controls";
import { Modal, CustomSelect, Field } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";

type Rule = {
  id: number; name: string; type: string; threshold: number;
  channel: string; target_url: string; target: string;
  is_active: boolean; cooldown_sec: number;
  last_triggered_at: string | null; created_at: string;
};
type AlertType = { id: string; label: string; unit: string; default_threshold: number; desc: string };
type Channel = { id: string; label: string; placeholder: string };
type Stats = {
  pending_deposits: number; error_rate_pct: number; cpu_percent: number; disk_percent: number;
  queue_stuck: number; bot_online: boolean; heartbeat_age_sec: number | null;
  total_errors_last_hour: number; total_gens_last_hour: number; gen_per_hour: number;
  checked_at: string; active_rules: number; alerts_24h: number;
};
type HistoryItem = { id: number; rule_id: number | null; rule_name: string | null; type: string; message: string; triggered_at: string; resolved: boolean; meta: any };

const TYPE_ICON: Record<string, any> = {
  error_rate: AlertTriangle, deposit_pending: DollarSign, cpu_high: Cpu, disk_high: HardDrive, queue_stuck: Layers, bot_offline: Bot,
};
const TYPE_COLOR: Record<string, string> = {
  error_rate: "text-red-500", deposit_pending: "text-amber-500", cpu_high: "text-orange-500", disk_high: "text-violet-500", queue_stuck: "text-yellow-500", bot_offline: "text-red-600",
};
const CHANNEL_ICON: Record<string, any> = { discord: Webhook, telegram: Send, webhook: Webhook };

export default function AlertsPage() {
  const { lang, t } = useLang();
  const [rules, setRules] = useState<Rule[]>([]);
  const [types, setTypes] = useState<AlertType[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  // modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Rule | null>(null);
  const [form, setForm] = useState({ name: "", type: "error_rate", threshold: 30, channel: "discord", target_url: "", cooldown_sec: 900, is_active: true });
  const [deleteTarget, setDeleteTarget] = useState<Rule | null>(null);
  const [testTarget, setTestTarget] = useState<Rule | null>(null);
  const [historyLimit, setHistoryLimit] = useState(50);

  const L = (id: string, fb: string, vars?: Record<string, any>) => {
    // try i18n first, fallback fb
    const tr = t(id, vars);
    if (tr === id) return fb;
    return tr;
  };

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [r, tcs, s, h] = await Promise.all([
        api("/api/alerts/rules").catch(() => ({ rules: [] })),
        api("/api/alerts/types").catch(() => ({ types: [], channels: [] })),
        api("/api/alerts/stats").catch(() => null),
        api(`/api/alerts/history?limit=${historyLimit}`).catch(() => ({ history: [] })),
      ]);
      setRules(r.rules || []);
      setTypes(tcs.types || []);
      setChannels(tcs.channels || []);
      if (s) setStats(s);
      setHistory(h.history || []);
    } catch (e: any) {
      toast.error(e.message || "Load failed");
    } finally {
      setLoading(false);
    }
  }, [historyLimit]);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { const id = setInterval(() => { api("/api/alerts/stats").then(setStats).catch(() => {}); }, 10000); return () => clearInterval(id); }, []);

  function openCreate() {
    setEditing(null);
    setForm({ name: "", type: "error_rate", threshold: (types.find(x => x.id === "error_rate")?.default_threshold || 30), channel: "discord", target_url: "", cooldown_sec: 900, is_active: true });
    setModalOpen(true);
  }
  function openEdit(rule: Rule) {
    setEditing(rule);
    setForm({ name: rule.name, type: rule.type, threshold: rule.threshold, channel: rule.channel, target_url: rule.target_url, cooldown_sec: rule.cooldown_sec, is_active: rule.is_active });
    setModalOpen(true);
  }

  async function saveRule() {
    if (!form.name.trim()) { toast.error(lang === "id" ? "Nama wajib" : "Name required"); return; }
    if (!form.target_url.trim()) { toast.error(lang === "id" ? "Target URL wajib" : "Target URL required"); return; }
    // basic url check
    const tr = form.target_url.trim();
    const isNumeric = /^-?\d{5,20}$/.test(tr);
    if (!isNumeric && !tr.startsWith("https://")) { toast.error(lang === "id" ? "Target harus https:// atau chat_id numerik Telegram" : "Target must be https:// or numeric telegram chat_id"); return; }
    setBusy(true);
    try {
      if (editing) {
        const res: any = await api(`/api/alerts/rules/${editing.id}`, { method: "PUT", body: JSON.stringify({ name: form.name.trim(), type: form.type, threshold: Number(form.threshold), channel: form.channel, target_url: tr, cooldown_sec: Number(form.cooldown_sec), is_active: form.is_active }) });
        setRules(prev => prev.map(r => r.id === editing.id ? res.rule : r));
        toast.success(lang === "id" ? "Rule diperbarui" : "Rule updated");
      } else {
        const res: any = await api(`/api/alerts/rules`, { method: "POST", body: JSON.stringify({ name: form.name.trim(), type: form.type, threshold: Number(form.threshold), channel: form.channel, target_url: tr, cooldown_sec: Number(form.cooldown_sec), is_active: form.is_active }) });
        setRules(prev => [res.rule, ...prev]);
        toast.success(lang === "id" ? "Rule dibuat" : "Rule created");
      }
      setModalOpen(false);
    } catch (e: any) {
      toast.error(e.message || "Save failed");
    } finally { setBusy(false); }
  }

  async function doDelete() {
    if (!deleteTarget) return;
    setBusy(true);
    try {
      await api(`/api/alerts/rules/${deleteTarget.id}`, { method: "DELETE" });
      setRules(prev => prev.filter(r => r.id !== deleteTarget.id));
      toast.success(lang === "id" ? "Rule dihapus" : "Rule deleted");
      setDeleteTarget(null);
    } catch (e: any) { toast.error(e.message); }
    finally { setBusy(false); }
  }

  async function toggle(rule: Rule) {
    try {
      const res: any = await api(`/api/alerts/rules/${rule.id}/toggle`, { method: "PATCH" });
      setRules(prev => prev.map(r => r.id === rule.id ? { ...r, is_active: res.is_active } : r));
      toast.success(res.is_active ? (lang === "id" ? "Diaktifkan" : "Enabled") : (lang === "id" ? "Dimatikan" : "Disabled"));
    } catch (e: any) { toast.error(e.message); }
  }

  async function doTest(rule: Rule) {
    setBusy(true);
    try {
      const res: any = await api(`/api/alerts/rules/${rule.id}/test`, { method: "POST" });
      if (res.ok) {
        toast.success(lang === "id" ? `Test terkirim: ${res.detail}` : `Test sent: ${res.detail}`);
        // refresh history
        const h: any = await api(`/api/alerts/history?limit=${historyLimit}`);
        setHistory(h.history || []);
      } else {
        toast.error(res.detail || res.message || "Test failed");
      }
      setTestTarget(null);
    } catch (e: any) { toast.error(e.message); }
    finally { setBusy(false); }
  }

  async function doEvaluate() {
    setEvaluating(true);
    try {
      const res: any = await api(`/api/alerts/evaluate`, { method: "POST" });
      if (res.triggered?.length) toast.success(`${res.triggered.length} ${lang === "id" ? "alert dipicu" : "alerts triggered"}`);
      else toast.info(lang === "id" ? "Tidak ada yang dipicu — semua aman" : "No triggers — all OK");
      if (res.stats) setStats((prev: any) => ({ ...prev, ...res.stats, active_rules: prev?.active_rules ?? res.stats.active_rules, alerts_24h: prev?.alerts_24h ?? 0 }));
      const h: any = await api(`/api/alerts/history?limit=${historyLimit}`);
      setHistory(h.history || []);
    } catch (e: any) { toast.error(e.message); }
    finally { setEvaluating(false); }
  }

  async function resolveHistory(id: number) {
    try {
      await api(`/api/alerts/history/${id}/resolve`, { method: "PATCH" });
      setHistory(prev => prev.map(h => h.id === id ? { ...h, resolved: true } : h));
    } catch (e: any) { toast.error(e.message); }
  }

  function handleTypeChange(newType: string) {
    const def = types.find(x => x.id === newType)?.default_threshold;
    setForm(f => ({ ...f, type: newType, threshold: def != null ? def : f.threshold }));
  }

  if (loading && !rules.length) return <PageLoader label={lang === "id" ? "Memuat..." : "Loading..."} cards={3} rows={4} />;

  return (
    <div className="flex flex-col gap-5 w-full max-w-full min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2"><Bell className="h-5 w-5 sm:h-6 sm:w-6" />{lang === "id" ? "Alert Webhook" : "Alert Webhook"}</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">{lang === "id" ? "Kelola rule notifikasi Discord / Telegram / Webhook + evaluasi live stats" : "Manage Discord / Telegram / Webhook rules + evaluate live stats"}</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={loadAll} className="h-8 text-xs"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button>
          <Button variant="outline" size="sm" onClick={doEvaluate} disabled={evaluating} className="h-8 text-xs"><Activity className={`h-4 w-4 ${evaluating ? "animate-spin" : ""}`} />{lang === "id" ? "Evaluasi" : "Evaluate"}</Button>
          <Button size="sm" onClick={openCreate} className="h-8 text-xs"><Plus className="h-4 w-4" />{lang === "id" ? "Tambah Rule" : "Add Rule"}</Button>
        </div>
      </div>

      {stats && (
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-5 w-full">
          <Card className={`w-full overflow-hidden ${!stats.bot_online ? "border-red-500/40" : "border-emerald-500/20"}`}><CardHeader className="pb-1"><CardTitle className="text-xs"><Bot className="h-4 w-4" />Bot</CardTitle></CardHeader><CardContent><div className={`text-lg font-bold flex items-center gap-1.5 ${stats.bot_online ? "text-emerald-500" : "text-destructive"}`}><span className={`h-2 w-2 rounded-full ${stats.bot_online ? "bg-emerald-500 animate-pulse" : "bg-red-500"}`} />{stats.bot_online ? "Online" : "Offline"}</div><div className="text-[11px] text-muted-foreground mt-1">hb {stats.heartbeat_age_sec != null ? `${stats.heartbeat_age_sec}s` : "no hb"}</div></CardContent></Card>
          <Card className="w-full overflow-hidden"><CardHeader className="pb-1"><CardTitle className="text-xs"><BarChart3 className="h-4 w-4" />Error Rate</CardTitle></CardHeader><CardContent><div className="text-lg font-bold">{stats.error_rate_pct}%</div><div className="text-[11px] text-muted-foreground">{stats.total_errors_last_hour}/{stats.total_gens_last_hour} last h</div></CardContent></Card>
          <Card className="w-full overflow-hidden"><CardHeader className="pb-1"><CardTitle className="text-xs"><DollarSign className="h-4 w-4" />Pending Deposit</CardTitle></CardHeader><CardContent><div className="text-lg font-bold">{stats.pending_deposits}</div><div className="text-[11px] text-muted-foreground">pending</div></CardContent></Card>
          <Card className="w-full overflow-hidden"><CardHeader className="pb-1"><CardTitle className="text-xs"><Cpu className="h-4 w-4" />CPU {stats.cpu_percent?.toFixed?.(0) ?? 0}%</CardTitle></CardHeader><CardContent><div className="text-lg font-bold">{(stats.cpu_percent ?? 0).toFixed(1)}%</div><div className="text-[11px] text-muted-foreground">disk {(stats.disk_percent ?? 0).toFixed(1)}%</div></CardContent></Card>
          <Card className="w-full overflow-hidden"><CardHeader className="pb-1"><CardTitle className="text-xs"><Layers className="h-4 w-4" />Queue Stuck</CardTitle></CardHeader><CardContent><div className="text-lg font-bold">{stats.queue_stuck}</div><div className="text-[11px] text-muted-foreground">active rules {stats.active_rules} · 24h {stats.alerts_24h}</div></CardContent></Card>
        </div>
      )}

      <div className="flex flex-col gap-3 w-full">
        {rules.length === 0 && <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">{lang === "id" ? "Belum ada rule. Tekan Tambah Rule." : "No rules yet. Click Add Rule."}</CardContent></Card>}
        {rules.map(rule => {
          const Icon = TYPE_ICON[rule.type] || Siren;
          const color = TYPE_COLOR[rule.type] || "text-muted-foreground";
          const ChIcon = CHANNEL_ICON[rule.channel] || Webhook;
          return (
            <Card key={rule.id} className={`w-full overflow-hidden transition-all ${!rule.is_active ? "opacity-60 bg-muted/20" : ""}`}>
              <CardContent className="p-3 sm:p-4 flex flex-col sm:flex-row sm:items-start gap-3">
                <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${rule.is_active ? "bg-primary/10" : "bg-muted"} ${color}`}><Icon className="h-5 w-5" /></div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-semibold text-sm">#{rule.id} {rule.name}</span>
                    <Badge variant={rule.is_active ? "muted" : "destructive"} className="text-[10px] flex items-center gap-1">{rule.is_active ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{rule.is_active ? "ON" : "OFF"}</Badge>
                    <Badge variant="muted" className="text-[10px]">{rule.type}</Badge>
                    <Badge variant="muted" className="text-[10px] flex items-center gap-1"><ChIcon className="h-3 w-3" />{rule.channel}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-0.5">
                    <span>thr <b className="text-foreground">{rule.threshold}</b> {rule.type.includes("_high") || rule.type === "error_rate" ? "%" : rule.type === "deposit_pending" || rule.type === "queue_stuck" ? "" : ""}</span>
                    <span className="flex items-center gap-1"><Timer className="h-3 w-3" /> cooldown {Math.round(rule.cooldown_sec / 60)}m</span>
                    <span className="truncate max-w-[280px]">target {rule.target_url.slice(0, 60)}{rule.target_url.length > 60 ? "…" : ""}</span>
                  </div>
                  {rule.last_triggered_at && <div className="text-[11px] text-muted-foreground mt-1">last {new Date(rule.last_triggered_at).toLocaleString(lang === "id" ? "id-ID" : "en-US")}</div>}
                </div>
                <div className="flex sm:flex-col gap-1.5 shrink-0">
                  <Button variant="outline" size="sm" className="h-7 text-xs flex-1 sm:flex-none" onClick={() => toggle(rule)}><Power className="h-3.5 w-3.5" />{rule.is_active ? "Off" : "On"}</Button>
                  <Button variant="outline" size="sm" className="h-7 text-xs flex-1 sm:flex-none" onClick={() => setTestTarget(rule)}><Send className="h-3.5 w-3.5" />Test</Button>
                  <Button variant="outline" size="sm" className="h-7 text-xs flex-1 sm:flex-none" onClick={() => openEdit(rule)}><Pencil className="h-3.5 w-3.5" />Edit</Button>
                  <Button variant="outline" size="sm" className="h-7 text-xs text-destructive flex-1 sm:flex-none" onClick={() => setDeleteTarget(rule)}><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card className="w-full overflow-hidden">
        <CardHeader className="pb-2"><CardTitle className="text-sm"><Clock className="h-4 w-4" />{lang === "id" ? "Riwayat Alert" : "Alert History"} <Badge variant="muted" className="ml-2 text-[10px]">REALTIME DB</Badge></CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-0 px-0 pt-0 max-w-full min-w-0">
          {history.length === 0 && <div className="py-8 text-center text-xs text-muted-foreground">{lang === "id" ? "Belum ada riwayat" : "No history yet"}</div>}
          {history.map(h => (
            <div key={h.id} className={`flex flex-col gap-1 border-b px-3 sm:px-5 py-2.5 text-xs w-full ${h.resolved ? "opacity-60" : ""}`}>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-medium">#{h.id}</span>
                <Badge variant="muted" className="text-[10px]">{h.type}</Badge>
                {h.rule_name && <Badge variant="muted" className="text-[10px]">{h.rule_name}</Badge>}
                {h.resolved ? <Badge variant="success" className="text-[10px]">resolved</Badge> : <Badge variant="default" className="text-[10px]">triggered</Badge>}
                <span className="text-muted-foreground text-[11px]">{new Date(h.triggered_at).toLocaleString(lang === "id" ? "id-ID" : "en-US")}</span>
                {!h.resolved && <Button variant="outline" size="sm" className="h-6 text-[10px] ml-auto" onClick={() => resolveHistory(h.id)}>Resolve</Button>}
              </div>
              <div className="text-[11px] sm:text-xs leading-snug break-all">{h.message.slice(0, 400)}</div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="rounded-lg border border-dashed p-2.5 sm:p-3 text-[11px] sm:text-xs text-muted-foreground flex items-start gap-2"><AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" /><span>{lang === "id" ? "Alert dicek on-demand via tombol Evaluasi (POST /api/alerts/evaluate) — hormati cooldown per rule (default 15m) anti spam. Test kirim langsung tanpa cek cooldown & threshold. Discord pakai {content}, Telegram chat_id numeric pakai BOT_TOKEN bot ini, Webhook generic JSON {text,message,meta}." : "Alerts evaluated on-demand via Evaluate button (POST /api/alerts/evaluate) — respects per-rule cooldown (default 15m) anti-spam. Test sends immediately ignoring cooldown. Discord uses {content}, Telegram numeric chat_id uses this bot's BOT_TOKEN, generic webhook JSON {text,message,meta}."}</span></div>

      {/* Create/Edit modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? (lang === "id" ? `Edit Rule #${editing.id}` : `Edit Rule #${editing.id}`) : (lang === "id" ? "Tambah Rule Alert" : "Add Alert Rule")}>
        <div className="flex flex-col gap-3">
          <Field label={lang === "id" ? "Nama Rule" : "Rule Name"}><Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder={lang === "id" ? "mis. CPU tinggi ke Discord" : "e.g. High CPU to Discord"} maxLength={100} /></Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label={lang === "id" ? "Tipe Alert" : "Alert Type"}><CustomSelect value={form.type} onChange={v => handleTypeChange(v)} options={(types.length ? types : [{ id: "error_rate", label: "Error Rate" }, { id: "deposit_pending", label: "Deposit Pending" }, { id: "cpu_high", label: "CPU High" }, { id: "disk_high", label: "Disk High" }, { id: "queue_stuck", label: "Queue Stuck" }, { id: "bot_offline", label: "Bot Offline" }]).map(t => ({ value: t.id, label: t.label }))} /></Field>
            <Field label={lang === "id" ? "Channel" : "Channel"}><CustomSelect value={form.channel} onChange={v => setForm(f => ({ ...f, channel: v }))} options={(channels.length ? channels : [{ id: "discord", label: "Discord" }, { id: "telegram", label: "Telegram" }, { id: "webhook", label: "Webhook" }]).map(c => ({ value: c.id, label: c.label }))} /></Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label={`Threshold ${form.type === "error_rate" || form.type.includes("high") ? "(%)" : form.type === "deposit_pending" || form.type === "queue_stuck" ? "(count)" : ""}`}><Input type="number" value={form.threshold} onChange={e => setForm(f => ({ ...f, threshold: Number(e.target.value) }))} min={0} max={1000000} step={form.type === "error_rate" ? 1 : 1} /></Field>
            <Field label={lang === "id" ? "Cooldown (detik)" : "Cooldown (sec)"}><Input type="number" value={form.cooldown_sec} onChange={e => setForm(f => ({ ...f, cooldown_sec: Number(e.target.value) }))} min={60} max={86400} step={60} /></Field>
          </div>
          <Field label={lang === "id" ? "Target URL / Chat ID" : "Target URL / Chat ID"}>
            <Textarea value={form.target_url} onChange={e => setForm(f => ({ ...f, target_url: e.target.value }))} placeholder={
              form.channel === "discord" ? "https://discord.com/api/webhooks/..." :
              form.channel === "telegram" ? "-100123456789 or https://... with chat_id query" :
              "https://example.com/webhook"
            } className="min-h-20" maxLength={1000} />
            <div className="text-[11px] text-muted-foreground mt-1">{lang === "id" ? "Discord: webhook URL. Telegram: chat_id numerik (pakai BOT_TOKEN env) atau https webhook. Webhook: https:// bebas (SSRF guard aktif, private IP diblokir)." : "Discord: webhook URL. Telegram: numeric chat_id (uses BOT_TOKEN) or https webhook. Webhook: any https:// (SSRF guard active)."}</div>
          </Field>
          <div className="flex items-center gap-2 mt-1"><input type="checkbox" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} id="active-check" /><label htmlFor="active-check" className="text-sm">{lang === "id" ? "Aktif" : "Active"}</label></div>
          <div className="flex gap-2 mt-2">
            <Button variant="outline" className="flex-1" onClick={() => setModalOpen(false)}>{lang === "id" ? "Batal" : "Cancel"}</Button>
            <Button className="flex-1" onClick={saveRule} disabled={busy}>{busy ? "..." : (lang === "id" ? "Simpan" : "Save")}</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title={lang === "id" ? "Hapus Rule?" : "Delete Rule?"} description={deleteTarget ? `${lang === "id" ? "Yakin hapus" : "Delete"} "${deleteTarget.name}"? ${lang === "id" ? "Tidak bisa dibatalkan." : "Cannot be undone."}` : ""} confirmLabel={lang === "id" ? "Ya, Hapus" : "Yes, Delete"} variant="destructive" loading={busy} onConfirm={doDelete} />
      <ConfirmDialog open={!!testTarget} onClose={() => setTestTarget(null)} title={lang === "id" ? "Kirim Test Alert?" : "Send Test Alert?"} description={testTarget ? `${lang === "id" ? "Kirim test ke" : "Send test to"} ${testTarget.channel} ${testTarget.target_url.slice(0, 80)}?` : ""} confirmLabel="Send Test" loading={busy} onConfirm={() => testTarget && doTest(testTarget)} />
    </div>
  );
}
