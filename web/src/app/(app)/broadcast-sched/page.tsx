"use client";
import { useEffect, useState, useRef, useMemo } from "react";
import { CalendarRange, Clock, Repeat, Send, Edit3, Trash2, Play, X, Eye, Search, History, Timer, AlertTriangle, CheckCircle2, Ban, Loader2, Users, Crown, UserCheck, Activity, Calendar, ImagePlus, Bold, Italic, Link2 } from "lucide-react";
import { PageLoader } from "@/components/ui/page-loader";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Badge } from "@/components/ui/controls";
import { Modal, Field, CustomSelect } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";

const TARGET_OPTS = [
  { v: "all", label: "All", icon: Users },
  { v: "premium", label: "Premium", icon: Crown },
  { v: "free", label: "Free", icon: UserCheck },
  { v: "active", label: "Active 7d", icon: Activity },
];
const REPEAT_OPTS = [
  { v: "once", label: "Once" },
  { v: "daily", label: "Daily" },
  { v: "weekly", label: "Weekly" },
  { v: "monthly", label: "Monthly" },
];
const STATUS_OPTS = [
  { v: "", labelAll: "All status" },
  { v: "pending" }, { v: "sent" }, { v: "sending" }, { v: "failed" }, { v: "cancelled" }
];

function fmtDate(iso?: string | null, lang: string = "id") {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString(lang === "id" ? "id-ID" : "en-US", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch { return iso || "—"; }
}
function fmtCountdown(nextIso?: string | null) {
  if (!nextIso) return "—";
  const now = Date.now();
  const t = new Date(nextIso).getTime();
  if (isNaN(t)) return "—";
  let diff = t - now;
  if (diff <= 0) return "Due now";
  const d = Math.floor(diff / 86400000); diff %= 86400000;
  const h = Math.floor(diff / 3600000); diff %= 3600000;
  const m = Math.floor(diff / 60000);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
function statusColor(s: string) {
  if (s === "pending") return "bg-amber-500/15 text-amber-600 border-amber-500/20";
  if (s === "sent") return "bg-emerald-500/15 text-emerald-600 border-emerald-500/20";
  if (s === "sending") return "bg-blue-500/15 text-blue-600 border-blue-500/20";
  if (s === "failed") return "bg-red-500/15 text-red-600 border-red-500/20";
  if (s === "cancelled") return "bg-zinc-500/15 text-zinc-500 border-zinc-500/20";
  return "bg-muted text-muted-foreground";
}
function repeatColor(r: string) {
  if (r === "once") return "bg-zinc-500/10 text-zinc-500";
  if (r === "daily") return "bg-sky-500/15 text-sky-600";
  if (r === "weekly") return "bg-violet-500/15 text-violet-600";
  if (r === "monthly") return "bg-fuchsia-500/15 text-fuchsia-600";
  return "bg-muted text-muted-foreground";
}

function previewHtml(text: string) {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const html = esc
    .replace(/&lt;b&gt;(.*?)&lt;\/b&gt;/gs, "<b>$1</b>")
    .replace(/&lt;i&gt;(.*?)&lt;\/i&gt;/gs, "<i>$1</i>")
    .replace(/&lt;u&gt;(.*?)&lt;\/u&gt;/gs, "<u>$1</u>")
    .replace(/&lt;s&gt;(.*?)&lt;\/s&gt;/gs, "<s>$1</s>")
    .replace(/&lt;a href=(?:&quot;|\\")(.*?)(?:&quot;|\\")&gt;(.*?)&lt;\/a&gt;/gs, (_m: string, href: string, inner: string) => {
      const low = href.trim().toLowerCase();
      if (low.startsWith("javascript:") || low.startsWith("data:")) return inner;
      if (!/^https?:\/\//.test(href) && !/^t\.me\//.test(href)) return inner;
      return `<a href="${href}" class="underline text-primary" target="_blank" rel="noreferrer">${inner}</a>`;
    })
    .replace(/\n/g, "<br/>");
  return { __html: html };
}

export default function BroadcastSchedPage() {
  const { t, lang } = useLang();
  const [schedules, setSchedules] = useState<any[]>([]);
  const [counts, setCounts] = useState<any>({});
  const [total, setTotal] = useState(0);
  const [pendingDue, setPendingDue] = useState(0);
  const [nextUp, setNextUp] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [repeatFilter, setRepeatFilter] = useState("");
  const [audienceCounts, setAudienceCounts] = useState<any>(null);

  // modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [targetType, setTargetType] = useState("all");
  const [scheduledAt, setScheduledAt] = useState(""); // datetime-local
  const [repeatType, setRepeatType] = useState("once");
  const [mediaFileId, setMediaFileId] = useState("");
  const [saving, setSaving] = useState(false);

  // actions
  const [confirmDel, setConfirmDel] = useState<any>(null);
  const [confirmCancel, setConfirmCancel] = useState<any>(null);
  const [confirmRun, setConfirmRun] = useState<any>(null);
  const [logsModal, setLogsModal] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [tick, setTick] = useState(0);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (targetFilter) params.set("target", targetFilter);
      if (repeatFilter) params.set("repeat", repeatFilter);
      if (q.trim()) params.set("q", q.trim());
      const qs = params.toString() ? `?${params.toString()}` : "";
      const r = await api(`/api/broadcast/schedules${qs}`);
      setSchedules(r.schedules || []);
      setCounts(r.counts || {});
      setTotal(r.total || 0);
      setPendingDue(r.pending_due || 0);
      setNextUp(r.next_upcoming || r.next || null);
    } catch (e: any) { toast.error(e.message || "Gagal load"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    api("/api/broadcast/audience-counts").then(setAudienceCounts).catch(() => {});
  }, []);
  // auto refresh if pending
  useEffect(() => {
    const hasPending = schedules.some((s) => s.status === "pending" || s.status === "sending");
    if (!hasPending) return;
    const id = setInterval(() => { setTick((x) => x + 1); }, 1000);
    const id2 = setInterval(() => { load(); }, 15000);
    return () => { clearInterval(id); clearInterval(id2); };
  }, [schedules]);

  useEffect(() => {
    const t = setTimeout(() => load(), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, statusFilter, targetFilter, repeatFilter]);

  function openAdd() {
    setEditing(null);
    setTitle("");
    setMessage("");
    setTargetType("all");
    // default scheduled_at = now + 1h in datetime-local
    const d = new Date(Date.now() + 3600 * 1000);
    const pad = (n: number) => String(n).padStart(2, "0");
    const local = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    setScheduledAt(local);
    setRepeatType("once");
    setMediaFileId("");
    setModalOpen(true);
  }
  function openEdit(s: any) {
    setEditing(s);
    setTitle(s.title || "");
    setMessage(s.message || "");
    setTargetType(s.target_type || "all");
    // convert ISO to local datetime-local
    try {
      const dt = new Date(s.scheduled_at);
      const pad = (n: number) => String(n).padStart(2, "0");
      const local = `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
      setScheduledAt(local);
    } catch { setScheduledAt(""); }
    setRepeatType(s.repeat_type || "once");
    setMediaFileId(s.media_file_id || "");
    setModalOpen(true);
  }

  async function save() {
    if (!message.trim()) return toast.error("Message wajib diisi");
    if (!scheduledAt) return toast.error("Scheduled_at wajib");
    const iso = new Date(scheduledAt).toISOString();
    if (isNaN(new Date(iso).getTime())) return toast.error("Tanggal invalid");
    if (mediaFileId.trim() && !/^[A-Za-z0-9_-]{10,400}$/.test(mediaFileId.trim())) return toast.error("media_file_id invalid regex ^[A-Za-z0-9_-]{10,400}$");
    setSaving(true);
    try {
      const payload: any = {
        title: title.trim() ? title.trim().slice(0, 100) : null,
        message: message.trim().slice(0, 4000),
        target_type: targetType,
        scheduled_at: iso,
        repeat_type: repeatType,
        media_file_id: mediaFileId.trim() || null,
      };
      if (editing) {
        await api(`/api/broadcast/schedules/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Schedule diupdate");
      } else {
        await api(`/api/broadcast/schedules`, { method: "POST", body: JSON.stringify(payload) });
        toast.success("Schedule dibuat");
      }
      setModalOpen(false);
      load();
    } catch (e: any) { toast.error(e.message || "Gagal simpan"); }
    finally { setSaving(false); }
  }

  async function doDelete() {
    if (!confirmDel) return;
    try {
      await api(`/api/broadcast/schedules/${confirmDel.id}`, { method: "DELETE" });
      toast.success("Dihapus");
      setConfirmDel(null);
      load();
    } catch (e: any) { toast.error(e.message || "Gagal hapus"); }
  }
  async function doCancel() {
    if (!confirmCancel) return;
    try {
      await api(`/api/broadcast/schedules/${confirmCancel.id}/cancel`, { method: "POST" });
      toast.success("Dibatalkan");
      setConfirmCancel(null);
      load();
    } catch (e: any) { toast.error(e.message || "Gagal cancel"); }
  }
  async function doRunNow() {
    if (!confirmRun) return;
    try {
      const r = await api(`/api/broadcast/schedules/${confirmRun.id}/run-now`, { method: "POST" });
      toast.success(`Terkirim ${r.sent}/${r.total}`);
      setConfirmRun(null);
      load();
    } catch (e: any) { toast.error(e.message || "Gagal run-now"); }
  }
  async function openLogs(s: any) {
    setLogsModal(s);
    setLogsLoading(true);
    try {
      const r = await api(`/api/broadcast/schedules/${s.id}/logs?limit=100`);
      setLogs(r.logs || []);
    } catch (e: any) { toast.error(e.message); }
    finally { setLogsLoading(false); }
  }
  async function doEvaluate() {
    setEvaluating(true);
    try {
      const r = await api(`/api/broadcast/schedules/evaluate`, { method: "POST" });
      toast.success(`Evaluate: ${r.count} processed`);
      load();
    } catch (e: any) { toast.error(e.message || "Gagal evaluate"); }
    finally { setEvaluating(false); }
  }

  const filteredInfo = useMemo(() => {
    const pending = counts["pending"] || 0;
    const sent = counts["sent"] || 0;
    const failed = counts["failed"] || 0;
    const cancelled = counts["cancelled"] || 0;
    return { pending, sent, failed, cancelled };
  }, [counts]);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2"><CalendarRange className="h-6 w-6" /> Broadcast Scheduler</h1>
          <p className="text-sm text-muted-foreground">Jadwalkan broadcast dengan repeat daily/weekly/monthly + retry + cron evaluate</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={doEvaluate} disabled={evaluating}>{evaluating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Timer className="h-4 w-4" />} Evaluate Due</Button>
          <Button onClick={openAdd}><Calendar className="h-4 w-4" /> Buat Jadwal</Button>
        </div>
      </div>

      {/* stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground uppercase">Total</div><div className="text-2xl font-bold">{total}</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground uppercase">Pending</div><div className="text-2xl font-bold text-amber-600">{filteredInfo.pending}</div><div className="text-[11px] text-muted-foreground">{pendingDue} due now</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground uppercase">Sent</div><div className="text-2xl font-bold text-emerald-600">{filteredInfo.sent}</div></CardContent></Card>
        <Card><CardContent className="p-4"><div className="text-xs text-muted-foreground uppercase">Failed</div><div className="text-2xl font-bold text-red-600">{filteredInfo.failed}</div></CardContent></Card>
        <Card className="col-span-2 lg:col-span-1">
          <CardContent className="p-4">
            <div className="text-xs text-muted-foreground uppercase flex items-center gap-1"><Clock className="h-3 w-3" /> Next</div>
            {nextUp ? (
              <div className="mt-1">
                <div className="text-sm font-semibold truncate">{nextUp.title || nextUp.message.slice(0, 30)}</div>
                <div className="text-[11px] text-muted-foreground">{fmtDate(nextUp.next_run_at, lang)}</div>
                <div className="text-xs font-bold text-primary">{fmtCountdown(nextUp.next_run_at)}</div>
              </div>
            ) : <div className="text-sm text-muted-foreground mt-1">Tidak ada pending</div>}
          </CardContent>
        </Card>
      </div>

      {/* filters */}
      <Card>
        <CardContent className="p-4 flex flex-col lg:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder="Cari title / message..." value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="flex gap-2 flex-wrap">
            <CustomSelect value={statusFilter} onChange={(v) => setStatusFilter(v)} placeholder="All status" options={[{ value: "", label: "All status" }, { value: "pending", label: "Pending" }, { value: "sent", label: "Sent" }, { value: "failed", label: "Failed" }, { value: "sending", label: "Sending" }, { value: "cancelled", label: "Cancelled" }]} className="w-[150px]" />
            <CustomSelect value={targetFilter} onChange={(v) => setTargetFilter(v)} placeholder="All targets" options={[{ value: "", label: "All targets" }, { value: "all", label: "All" }, { value: "premium", label: "Premium" }, { value: "free", label: "Free" }, { value: "active", label: "Active 7d" }]} className="w-[150px]" />
            <CustomSelect value={repeatFilter} onChange={(v) => setRepeatFilter(v)} placeholder="All repeat" options={[{ value: "", label: "All repeat" }, { value: "once", label: "Once" }, { value: "daily", label: "Daily" }, { value: "weekly", label: "Weekly" }, { value: "monthly", label: "Monthly" }]} className="w-[130px]" />
          </div>
        </CardContent>
      </Card>

      {/* list */}
      {loading ? <PageLoader label="Memuat..." rows={3} /> : schedules.length === 0 ? (
        <Card><CardContent className="p-8 text-center text-muted-foreground text-sm">Tidak ada jadwal. Buat jadwal baru.</CardContent></Card>
      ) : (
        <div className="grid gap-3">
          {schedules.map((s) => {
            const isDue = s.status === "pending" && s.next_run_at && new Date(s.next_run_at).getTime() <= Date.now();
            return (
              <Card key={s.id} className={isDue ? "border-amber-500/50" : ""}>
                <CardContent className="p-4 flex flex-col gap-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm truncate">{s.title || `Schedule #${s.id}`}</span>
                        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${statusColor(s.status)}`}>{s.status}</span>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${repeatColor(s.repeat_type)}`}><Repeat className="h-3 w-3 mr-1" />{s.repeat_type}</span>
                        {isDue && <span className="inline-flex items-center rounded-full bg-amber-500 text-white px-2 py-0.5 text-[10px] font-bold">DUE</span>}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground line-clamp-2">{s.message.slice(0, 120)}{s.message.length > 80 ? "…" : ""}</div>
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                        <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-1"><Users className="h-3 w-3" />{s.target_type}</span>
                        <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-1"><Clock className="h-3 w-3" />{fmtDate(s.scheduled_at, lang)}</span>
                        <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-1"><Timer className="h-3 w-3" />next {fmtDate(s.next_run_at, lang)} · {fmtCountdown(s.next_run_at)}</span>
                        {s.retry_count > 0 && <span className="inline-flex items-center gap-1 rounded bg-red-500/10 text-red-600 px-2 py-1">Retry {s.retry_count}/{s.max_retries} {s.failure_reason ? `· ${s.failure_reason.slice(0, 40)}` : ""}</span>}
                      </div>
                    </div>
                    <div className="flex gap-1 shrink-0 flex-wrap justify-end">
                      <Button size="sm" variant="outline" onClick={() => openLogs(s)}><History className="h-3.5 w-3.5" /></Button>
                      {s.status !== "sending" && <Button size="sm" variant="outline" onClick={() => openEdit(s)}><Edit3 className="h-3.5 w-3.5" /></Button>}
                      {s.status === "pending" && <Button size="sm" variant="outline" className="text-blue-600" onClick={() => setConfirmRun(s)}><Play className="h-3.5 w-3.5" /> Run</Button>}
                      {s.status === "pending" && <Button size="sm" variant="outline" className="text-amber-600" onClick={() => setConfirmCancel(s)}><Ban className="h-3.5 w-3.5" /></Button>}
                      <Button size="sm" variant="outline" className="text-destructive" onClick={() => setConfirmDel(s)}><Trash2 className="h-3.5 w-3.5" /></Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Add/Edit Modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? `Edit #${editing.id}` : "Buat Jadwal Broadcast"}>
        <div className="flex flex-col gap-4">
          <Field label="Title (opsional, max 100)">
            <Input placeholder="Contoh: Promo weekend" value={title} onChange={(e) => setTitle(e.target.value.slice(0, 100))} />
          </Field>
          <Field label="Message * (1-4000, HTML b,i,u,s,code,pre allowed)">
            <div className="flex gap-1 mb-2">
              <Button type="button" size="sm" variant="outline" onClick={() => setMessage((m) => `${m}<b></b>`)}><Bold className="h-3 w-3" />Bold</Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setMessage((m) => `${m}<i></i>`)}><Italic className="h-3 w-3" />Italic</Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setMessage((m) => `${m}<a href="https://">link</a>`)}><Link2 className="h-3 w-3" />Link</Button>
            </div>
            <Textarea rows={5} value={message} onChange={(e) => setMessage(e.target.value.slice(0, 4000))} placeholder="Tulis pesan broadcast..." />
            <div className="text-right text-[11px] text-muted-foreground mt-1">{message.length}/4000</div>
            {message.trim() && <div className="rounded-md border bg-muted/40 p-3 mt-2 text-sm leading-relaxed" dangerouslySetInnerHTML={previewHtml(message)} />}
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Target">
              <CustomSelect value={targetType} onChange={setTargetType} options={[{ value: "all", label: `All (${audienceCounts?.all ?? "…"})` }, { value: "premium", label: `Premium (${audienceCounts?.premium ?? "…"})` }, { value: "free", label: `Free (${audienceCounts?.free ?? "…"})` }, { value: "active", label: `Active 7d (${audienceCounts?.active ?? "…"})` }]} />
            </Field>
            <Field label="Repeat">
              <CustomSelect value={repeatType} onChange={setRepeatType} options={REPEAT_OPTS.map((o) => ({ value: o.v, label: o.label }))} />
            </Field>
          </div>
          <Field label="Scheduled At * (local time, akan konvert ke ISO UTC)">
            <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
          </Field>
          <Field label="Media File ID opsional (regex ^[A-Za-z0-9_-]{10,400}$)">
            <Input placeholder="File ID foto Telegram opsional" value={mediaFileId} onChange={(e) => setMediaFileId(e.target.value.trim())} />
          </Field>
          <div className="flex gap-2 pt-2">
            <Button variant="outline" className="flex-1" onClick={() => setModalOpen(false)}>Batal</Button>
            <Button className="flex-1" onClick={save} disabled={saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Simpan</Button>
          </div>
        </div>
      </Modal>

      {/* Confirm dialogs */}
      <ConfirmDialog open={!!confirmDel} onClose={() => setConfirmDel(null)} onConfirm={doDelete} title="Hapus Schedule" variant="destructive" confirmLabel="Ya, Hapus" description={`Yakin hapus ${confirmDel?.title || `#${confirmDel?.id}`} ?`} />
      <ConfirmDialog open={!!confirmCancel} onClose={() => setConfirmCancel(null)} onConfirm={doCancel} title="Cancel Schedule" variant="destructive" confirmLabel="Ya, Cancel" description="Jadwal akan dibatalkan dan tidak dikirim lagi." />
      <ConfirmDialog open={!!confirmRun} onClose={() => setConfirmRun(null)} onConfirm={doRunNow} title="Run Now" variant="default" confirmLabel="Ya, Kirim Sekarang" description={`Kirim ${confirmRun?.title || `#${confirmRun?.id}`} sekarang ke target ${confirmRun?.target_type}? Menggunakan flow broadcast real.`} />

      {/* Logs */}
      <Modal open={!!logsModal} onClose={() => setLogsModal(null)} title={`Logs #${logsModal?.id} — ${logsModal?.title || ""}`}>
        {logsLoading ? <PageLoader label="Memuat..." rows={2} cards={0} /> : logs.length === 0 ? <div className="text-sm text-muted-foreground">Belum ada logs</div> : (
          <div className="flex flex-col gap-2 max-h-[60vh] overflow-y-auto">
            {logs.map((l: any) => (
              <div key={l.id} className="rounded-md border p-3 text-xs">
                <div className="flex items-center gap-2"><span className={`rounded-full px-2 py-0.5 text-[10px] font-bold border ${statusColor(l.status)}`}>{l.status}</span><span className="text-muted-foreground">{fmtDate(l.run_at, lang)}</span></div>
                <div className="mt-1">sent {l.sent_count} / failed {l.failed_count} {l.error_message ? `· ${l.error_message}` : ""}</div>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
