"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { HardDrive, Download, Trash2, RefreshCw, AlertTriangle, Clock, CheckCircle2, Database, Archive, XCircle, Loader2, ShieldAlert, FileArchive, Clock3, UploadCloud, RotateCcw, FileCheck } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Badge } from "@/components/ui/controls";
import { Modal, Field } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";

type Backup = {
  id: number; filename: string; size_bytes: number; size_human: string;
  type: "manual" | "auto" | "upload";
  status: "in_progress" | "completed" | "failed" | "restoring";
  storage_path: string; checksum: string; checksum_short: string;
  created_by: string; created_at: string; completed_at: string | null; error_message: string | null; file_exists: boolean; meta: any;
};
type Stats = {
  total_backups: number; total_size_bytes: number; total_size_human: string;
  last_backup: Backup | null; pending_count: number; failed_count: number;
  auto_backup_enabled: boolean; needs_auto_backup: boolean; backup_dir: string; last_backup_ago_hours: number | null;
};

function timeAgo(iso: string, lang: string): string {
  try {
    const d = new Date(iso); const now = new Date(); const s = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (s < 60) return lang === "id" ? "Baru saja" : "Just now";
    if (s < 3600) return lang === "id" ? `${Math.floor(s / 60)}m lalu` : `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return lang === "id" ? `${Math.floor(s / 3600)}j lalu` : `${Math.floor(s / 3600)}h ago`;
    return lang === "id" ? `${Math.floor(s / 86400)}h lalu` : `${Math.floor(s / 86400)}d ago`;
  } catch { return iso; }
}
function StatusBadge({ status, lang }: { status: string; lang: string }) {
  const m: Record<string, { label: string; color: string; icon: any }> = {
    completed: { label: lang === "id" ? "Selesai" : "Completed", color: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-200", icon: CheckCircle2 },
    in_progress: { label: lang === "id" ? "Proses" : "In progress", color: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-200", icon: Loader2 },
    restoring: { label: "Restore", color: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-200", icon: Loader2 },
    failed: { label: lang === "id" ? "Gagal" : "Failed", color: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-200", icon: XCircle },
  };
  const cfg = m[status] || { label: status, color: "bg-muted", icon: Clock };
  const Icon = cfg.icon;
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border ${cfg.color}`}><Icon className={`h-3 w-3 ${status === "in_progress" || status === "restoring" ? "animate-spin" : ""}`} />{cfg.label}</span>;
}
function TypeBadge({ t }: { t: string }) {
  const c = t === "auto" ? "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950 dark:text-violet-200" : t === "upload" ? "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-200" : "bg-zinc-50 text-zinc-700 border-zinc-200 dark:bg-zinc-900";
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium border ${c}`}>{t}</span>;
}

export default function BackupPage() {
  const { lang } = useLang();
  const [backups, setBackups] = useState<Backup[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Backup | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<Backup | null>(null);
  const [restoreConfirmText, setRestoreConfirmText] = useState("");
  const [restoreSafety, setRestoreSafety] = useState(true);
  const [restoreStep, setRestoreStep] = useState<1 | 2>(1);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [listRes, statsRes] = await Promise.all([
        api("/api/backup/list").catch(() => ({ backups: [] })),
        api("/api/backup/stats").catch(() => null),
      ]);
      setBackups(listRes.backups || []); if (statsRes) setStats(statsRes);
    } catch (e: any) { toast.error(e.message || "Load failed"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => {
    const active = backups.some(b => b.status === "in_progress" || b.status === "restoring");
    if (!active) return;
    const id = setInterval(() => {
      api("/api/backup/list").then(r => setBackups(r.backups || [])).catch(() => {});
      api("/api/backup/stats").then(setStats).catch(() => {});
    }, 10000);
    return () => clearInterval(id);
  }, [backups]);

  async function handleCreate() {
    setCreating(true);
    try {
      const res: any = await api("/api/backup/create", { method: "POST", body: JSON.stringify({ type: "manual" }) });
      setBackups(prev => [res.backup, ...prev]); toast.success(lang === "id" ? `Backup dibuat: ${res.backup.filename}` : `Backup created: ${res.backup.filename}`);
      const s: any = await api("/api/backup/stats").catch(() => null); if (s) setStats(s);
    } catch (e: any) { toast.error(e.message || "Create failed"); }
    finally { setCreating(false); }
  }
  async function handleDelete() {
    if (!deleteTarget) return; setBusy(true);
    try {
      await api(`/api/backup/${deleteTarget.id}`, { method: "DELETE" });
      setBackups(prev => prev.filter(b => b.id !== deleteTarget.id)); toast.success(lang === "id" ? "Backup dihapus" : "Deleted"); setDeleteTarget(null);
      const s: any = await api("/api/backup/stats").catch(() => null); if (s) setStats(s);
    } catch (e: any) { toast.error((e as any).message); }
    finally { setBusy(false); }
  }
  async function handleDownload(b: Backup) {
    try {
      const res = await fetch(`/api/backup/${b.id}/download`, { credentials: "include" });
      if (!res.ok) { const j = await res.json().catch(() => ({ detail: "Download failed" })); throw new Error(j.detail || `HTTP ${res.status}`); }
      const blob = await res.blob(); const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = b.filename; document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
      toast.success(lang === "id" ? "Download dimulai" : "Download started");
    } catch (e: any) { toast.error(e.message || "Download failed"); }
  }
  async function handleRestore() {
    if (!restoreTarget) return;
    if (restoreConfirmText !== "RESTORE") { toast.error(lang === "id" ? "Ketik RESTORE untuk konfirmasi" : "Type RESTORE to confirm"); return; }
    setBusy(true);
    try {
      const res: any = await api(`/api/backup/${restoreTarget.id}/restore`, { method: "POST", body: JSON.stringify({ confirm: true, create_safety_backup: restoreSafety }) });
      toast.success(lang === "id" ? `Restore berhasil: ${res.restored}` : `Restore OK: ${res.restored}`);
      setRestoreTarget(null); setRestoreConfirmText(""); setRestoreStep(1); loadAll();
    } catch (e: any) { toast.error(e.message || "Restore failed"); }
    finally { setBusy(false); }
  }
  async function handleUpload(file: File) {
    if (!file) return;
    if (file.size > 500 * 1024 * 1024) { toast.error(lang === "id" ? "File >500MB tidak diizinkan" : "File >500MB not allowed"); return; }
    setUploading(true);
    try {
      const form = new FormData(); form.append("file", file);
      const res = await fetch("/api/backup/upload", { method: "POST", body: form, credentials: "include" });
      if (!res.ok) { const j = await res.json().catch(() => ({ detail: "Upload failed" })); throw new Error(j.detail || `HTTP ${res.status}`); }
      const data: any = await res.json(); setBackups(prev => [data.backup, ...prev]); toast.success(lang === "id" ? `Upload OK: ${data.backup.filename}` : `Upload OK: ${data.backup.filename}`);
      const s: any = await api("/api/backup/stats").catch(() => null); if (s) setStats(s);
    } catch (e: any) { toast.error(e.message || "Upload failed"); }
    finally { setUploading(false); if (fileInputRef.current) fileInputRef.current.value = ""; }
  }
  async function handleEvaluateAuto(force = false) {
    setEvaluating(true);
    try {
      const res: any = await api(`/api/backup/evaluate-auto?force=${force}`, { method: "POST" });
      if (res.created) { setBackups(prev => [res.backup, ...prev]); toast.success(lang === "id" ? `Auto backup dibuat: ${res.backup.filename}` : `Auto backup created: ${res.backup.filename}`); }
      else { toast.info(res.reason || (lang === "id" ? "Belum perlu backup" : "No backup needed")); }
      const s: any = await api("/api/backup/stats").catch(() => null); if (s) setStats(s);
    } catch (e: any) { toast.error(e.message || "Evaluate failed"); }
    finally { setEvaluating(false); }
  }

  if (loading && !backups.length)
    return <div className="py-20 text-center text-sm text-muted-foreground flex flex-col items-center gap-2 w-full"><RefreshCw className="h-5 w-5 animate-spin" />{lang === "id" ? "Memuat backup..." : "Loading backups..."}</div>;

  return (
    <div className="flex flex-col gap-5 w-full max-w-full overflow-hidden">
      {/* header MATCH system/failover */}
      <div className="flex flex-wrap items-start justify-between gap-3 w-full">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2"><HardDrive className="h-5 w-5 sm:h-6 sm:w-6" />{lang === "id" ? "Backup & Restore" : "Backup & Restore"}</h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">{lang === "id" ? "Dump DB via pg_dump .sql.gz, download/restore/upload. Restore overwrite DB — konfirmasi ganda." : "pg_dump compressed .sql.gz, download/restore/upload. Restore overwrites DB — double confirm."}</p>
        </div>
        <div className="flex gap-2 shrink-0 flex-wrap">
          <Button variant="outline" size="sm" onClick={loadAll} className="h-8 text-xs"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</Button>
          <Button variant="outline" size="sm" onClick={() => handleEvaluateAuto(false)} disabled={evaluating} className="h-8 text-xs"><Clock3 className={`h-4 w-4 ${evaluating ? "animate-spin" : ""}`} />{lang === "id" ? "Cek Auto" : "Check Auto"}</Button>
          <Button variant="outline" size="sm" onClick={() => handleEvaluateAuto(true)} disabled={evaluating || creating} className="h-8 text-xs"><Archive className="h-4 w-4" />Force</Button>
          <Button size="sm" onClick={handleCreate} disabled={creating || uploading} className="h-8 text-xs"><Database className={`h-4 w-4 ${creating ? "animate-spin" : ""}`} />{creating ? (lang === "id" ? "Membuat..." : "Creating...") : (lang === "id" ? "Buat Backup" : "Create")}</Button>
          <label className="inline-flex">
            <input ref={fileInputRef} type="file" accept=".sql.gz,.gz,.dump,.sql" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); }} />
            <span onClick={() => fileInputRef.current?.click()} className={`inline-flex h-8 items-center gap-1.5 rounded-md bg-secondary text-secondary-foreground px-3 text-xs font-medium cursor-pointer hover:opacity-80 ${uploading ? "opacity-50 pointer-events-none" : ""}`}><UploadCloud className={`h-4 w-4 ${uploading ? "animate-spin" : ""}`} />Upload</span>
          </label>
        </div>
      </div>

      {/* warning — MATCH failover.how info box pattern */}
      <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/40 p-4 flex gap-3 text-sm text-amber-800 dark:text-amber-200">
        <AlertTriangle className="h-5 w-5 shrink-0" />
        <div className="space-y-1 text-xs sm:text-sm">
          <div className="font-semibold">{lang === "id" ? "Perhatian Restore" : "Restore Warning"}</div>
          <ul className="list-disc ml-4 space-y-0.5 text-[12px] sm:text-[13px]">
            <li>{lang === "id" ? "Restore overwrite seluruh DB — data sekarang tertimpa backup." : "Restore overwrites entire DB — current data replaced."}</li>
            <li>{lang === "id" ? "Disarankan download backup dulu sebelum restore." : "Strongly suggest download first."}</li>
            <li>{lang === "id" ? "Sistem auto buat safety backup sebelum restore jika opsi aktif." : "System auto safety backup before restore if enabled."}</li>
          </ul>
        </div>
      </div>

      {/* stats MATCH system 3-col */}
      {stats && (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 w-full">
          <Card className="w-full overflow-hidden"><CardHeader><CardTitle><FileArchive className="h-4 w-4" />{lang === "id" ? "Total Backup" : "Total Backups"}</CardTitle></CardHeader><CardContent className="flex flex-col gap-1"><div className="text-2xl font-bold tracking-tight">{stats.total_backups}</div><div className="text-xs text-muted-foreground">{stats.pending_count} pending · {stats.failed_count} failed</div></CardContent></Card>
          <Card className="w-full overflow-hidden"><CardHeader><CardTitle><HardDrive className="h-4 w-4" />{lang === "id" ? "Total Ukuran" : "Total Size"}</CardTitle></CardHeader><CardContent className="flex flex-col gap-1"><div className="text-2xl font-bold tracking-tight">{stats.total_size_human}</div><div className="text-xs text-muted-foreground truncate">{stats.backup_dir}</div></CardContent></Card>
          <Card className="w-full overflow-hidden"><CardHeader><CardTitle><Clock className="h-4 w-4" />{lang === "id" ? "Terakhir" : "Last Backup"}</CardTitle></CardHeader><CardContent className="flex flex-col gap-1"><div className="text-sm font-medium truncate">{stats.last_backup ? stats.last_backup.filename : (lang === "id" ? "Belum ada" : "None")}</div><div className="text-xs text-muted-foreground">{stats.last_backup ? timeAgo(stats.last_backup.created_at, lang) : "-"} · <span className={stats.needs_auto_backup ? "text-amber-600 font-semibold" : "text-emerald-600"}>{stats.needs_auto_backup ? (lang === "id" ? "Butuh auto" : "Needs auto") : "OK"}</span></div></CardContent></Card>
          <Card className="w-full overflow-hidden"><CardHeader><CardTitle><ShieldAlert className="h-4 w-4" />Auto Backup</CardTitle></CardHeader><CardContent className="flex flex-col gap-1"><div className="text-sm font-medium flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${stats.auto_backup_enabled ? "bg-emerald-500" : "bg-zinc-400"}`} />{stats.auto_backup_enabled ? (lang === "id" ? "Aktif" : "Enabled") : "Disabled"}</div><div className="text-xs text-muted-foreground">{lang === "id" ? "Cek >24j otomatis" : "Check >24h auto"}</div></CardContent></Card>
        </div>
      )}

      <Card className="w-full overflow-hidden">
        <CardHeader><CardTitle><Archive className="h-4 w-4" />{lang === "id" ? "Daftar Backup" : "Backup List"} <Badge variant="outline" className="ml-2 text-[11px]">{backups.length}</Badge></CardTitle></CardHeader>
        <CardContent className="p-0">
          <div className="hidden md:block w-full overflow-x-auto"><table className="w-full text-sm min-w-[700px]"><thead className="border-b bg-muted/30 text-[11px] text-muted-foreground"><tr><th className="px-5 py-2.5 text-left font-medium">File</th><th className="px-4 py-2.5 text-left font-medium">Size</th><th className="px-4 py-2.5 text-left font-medium">Type</th><th className="px-4 py-2.5 text-left font-medium">Status</th><th className="px-4 py-2.5 text-left font-medium">Created</th><th className="px-4 py-2.5 text-left font-medium">By</th><th className="px-4 py-2.5 text-left font-medium">Checksum</th><th className="px-5 py-2.5 text-right font-medium">Actions</th></tr></thead><tbody className="divide-y">{backups.length === 0 && <tr><td colSpan={8} className="py-10 text-center text-muted-foreground text-sm">{lang === "id" ? "Belum ada backup" : "No backups"}</td></tr>}{backups.map(b => <tr key={b.id} className="hover:bg-muted/50"><td className="px-5 py-3 max-w-[220px] truncate font-mono text-xs" title={b.filename}>{b.filename}{!b.file_exists && b.status === "completed" && <span className="ml-1 text-amber-600">⚠</span>}</td><td className="px-4 py-3 whitespace-nowrap text-xs">{b.size_human}</td><td className="px-4 py-3"><TypeBadge t={b.type} /></td><td className="px-4 py-3"><StatusBadge status={b.status} lang={lang} />{b.error_message && <div className="text-[10px] text-red-600 max-w-[160px] truncate mt-1" title={b.error_message}>{b.error_message.slice(0, 80)}</div>}</td><td className="px-4 py-3 whitespace-nowrap text-xs text-muted-foreground">{new Date(b.created_at).toLocaleString(lang === "id" ? "id-ID" : "en-US")}<div className="text-[11px]">{timeAgo(b.created_at, lang)}</div></td><td className="px-4 py-3 text-xs truncate max-w-[80px]">{b.created_by || "-"}</td><td className="px-4 py-3 font-mono text-[11px] text-muted-foreground" title={b.checksum}>{b.checksum_short || "-"}</td><td className="px-5 py-3"><div className="flex justify-end gap-1"><Button variant="outline" size="sm" className="h-7 px-2 text-[11px]" disabled={!b.file_exists && b.status !== "completed"} onClick={() => handleDownload(b)}><Download className="h-3.5 w-3.5" /></Button><Button variant="outline" size="sm" className="h-7 px-2 text-[11px]" disabled={b.status === "in_progress" || b.status === "restoring" || !b.file_exists} onClick={() => { setRestoreTarget(b); setRestoreStep(1); setRestoreConfirmText(""); setRestoreSafety(true); }}><RotateCcw className="h-3.5 w-3.5" /></Button><Button variant="outline" size="sm" className="h-7 px-2 text-[11px]" disabled={b.status === "in_progress" || b.status === "restoring"} onClick={() => setDeleteTarget(b)}><Trash2 className="h-3.5 w-3.5" /></Button></div></td></tr>)}</tbody></table></div>
          <div className="md:hidden flex flex-col gap-3 p-3 w-full">
            {backups.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground">{lang === "id" ? "Belum ada backup" : "No backups yet"}</div>}
            {backups.map(b => (
              <div key={b.id} className="rounded-lg border bg-card p-4 flex flex-col gap-2.5 w-full">
                <div className="flex items-start justify-between gap-2"><div className="min-w-0 flex-1"><div className="font-mono text-xs font-medium truncate">{b.filename}</div><div className="flex flex-wrap items-center gap-1.5 mt-1.5"><TypeBadge t={b.type} /><StatusBadge status={b.status} lang={lang} /><span className="text-xs text-muted-foreground">{b.size_human}</span></div></div><div className="text-[11px] text-muted-foreground text-right shrink-0">{timeAgo(b.created_at, lang)}<br /><span className="font-mono text-[10px]">{b.checksum_short}</span></div></div>
                {b.error_message && <div className="text-xs text-red-600 bg-red-50 dark:bg-red-950/30 border border-red-200 rounded p-2 break-all">{b.error_message.slice(0, 200)}</div>}
                <div className="text-xs text-muted-foreground flex items-center gap-2"><Clock className="h-3 w-3" />{new Date(b.created_at).toLocaleString(lang === "id" ? "id-ID" : "en-US")} · {b.created_by || "-"} {b.file_exists ? <FileCheck className="h-3 w-3 text-emerald-600" /> : <span className="text-amber-600 text-[10px]">⚠ missing</span>}</div>
                <div className="flex gap-2 pt-1"><Button variant="outline" size="sm" className="flex-1 h-8 text-xs" onClick={() => handleDownload(b)} disabled={!b.file_exists && b.status !== "completed"}><Download className="h-4 w-4" />DL</Button><Button variant="outline" size="sm" className="flex-1 h-8 text-xs" onClick={() => { setRestoreTarget(b); setRestoreStep(1); setRestoreConfirmText(""); setRestoreSafety(true); }} disabled={b.status === "in_progress" || b.status === "restoring" || !b.file_exists}><RotateCcw className="h-4 w-4" />Restore</Button><Button variant="outline" size="sm" className="h-8 w-8 px-0" onClick={() => setDeleteTarget(b)} disabled={b.status === "in_progress" || b.status === "restoring"}><Trash2 className="h-4 w-4" /></Button></div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title={lang === "id" ? "Hapus Backup?" : "Delete Backup?"} description={deleteTarget ? (lang === "id" ? `Yakin hapus ${deleteTarget.filename}? File di disk juga akan dihapus.` : `Delete ${deleteTarget.filename}? File on disk will be removed.`) : ""} confirmLabel={lang === "id" ? "Ya, Hapus" : "Yes, Delete"} variant="destructive" loading={busy} onConfirm={handleDelete} />

      {restoreTarget && (
        <Modal open={!!restoreTarget} onClose={() => { setRestoreTarget(null); setRestoreConfirmText(""); setRestoreStep(1); }} title={restoreStep === 1 ? (lang === "id" ? "Konfirmasi Restore" : "Confirm Restore") : (lang === "id" ? "Ketik RESTORE" : "Type RESTORE")}>
          <div className="flex flex-col gap-4">
            {restoreStep === 1 && (
              <>
                <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/40 p-4 flex gap-3 text-sm text-amber-800 dark:text-amber-200"><AlertTriangle className="h-5 w-5 shrink-0" /><div className="space-y-1"><div className="font-semibold">{lang === "id" ? "Restore akan overwrite DB!" : "Restore will overwrite DB!"}</div><div className="text-xs">File: {restoreTarget.filename} ({restoreTarget.size_human})</div><div className="text-xs opacity-80">{lang === "id" ? "Disarankan download backup dulu." : "Suggest download first."}</div></div></div>
                <div className="flex items-center gap-2 text-sm"><input type="checkbox" id="safety" checked={restoreSafety} onChange={e => setRestoreSafety(e.target.checked)} className="h-4 w-4 rounded border-input" /><label htmlFor="safety" className="cursor-pointer">{lang === "id" ? "Buat safety backup dulu (disarankan)" : "Create safety backup first"}</label></div>
                <div className="flex gap-2 justify-end"><Button variant="outline" size="sm" onClick={() => { setRestoreTarget(null); setRestoreStep(1); }}>{lang === "id" ? "Batal" : "Cancel"}</Button><Button size="sm" variant="destructive" onClick={() => setRestoreStep(2)}><AlertTriangle className="h-4 w-4" />{lang === "id" ? "Lanjut — Ketik RESTORE" : "Continue — Type RESTORE"}</Button></div>
              </>
            )}
            {restoreStep === 2 && (
              <>
                <p className="text-sm text-muted-foreground">{lang === "id" ? `Ketik RESTORE (huruf besar) untuk konfirmasi restore file ${restoreTarget.filename}.` : `Type RESTORE to confirm restore ${restoreTarget.filename}.`}</p>
                <Field label="Konfirmasi"><Input value={restoreConfirmText} onChange={e => setRestoreConfirmText(e.target.value)} placeholder="RESTORE" className="font-mono" /></Field>
                <div className="flex gap-2 justify-end"><Button variant="outline" size="sm" onClick={() => setRestoreStep(1)}>{lang === "id" ? "Kembali" : "Back"}</Button><Button size="sm" variant="destructive" disabled={busy || restoreConfirmText !== "RESTORE"} onClick={handleRestore}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}{lang === "id" ? "Ya, Restore Sekarang" : "Yes, Restore Now"}</Button></div>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
