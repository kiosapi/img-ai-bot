"use client";
import { useEffect, useState, useMemo } from "react";
import { ShieldAlert, Ban, Search, Plus, Edit3, Trash2, Power, RefreshCw, Filter, AlertTriangle, Tag, Type, Regex, Hash, Eye, Calendar, User, Clock } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Badge, Switch } from "@/components/ui/controls";
import { Modal, Field, CustomSelect } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";
import { PageLoader } from "@/components/ui/page-loader";

type Rule = {
  id: number;
  pattern: string;
  type: "word" | "regex" | "category";
  severity: "low" | "medium" | "high" | "block";
  is_active: boolean;
  created_at: string;
};
type LogItem = {
  id: number;
  user_id: number;
  prompt: string;
  matched_pattern: string;
  rule_id: number | null;
  action: string;
  created_at: string;
};

const TYPE_OPTIONS = [
  { value: "word", label: "Word (contains, case-insensitive)" },
  { value: "regex", label: "Regex (Python, IGNORECASE)" },
  { value: "category", label: "Category (nsfw/politic/selfharm)" },
];
const SEV_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High (block)" },
  { value: "block", label: "Block" },
];
const EMPTY_FORM = { id: 0, pattern: "", type: "word", severity: "block", is_active: true };

function testPattern(pattern: string, type: string, input: string): { match: boolean; matched?: string; error?: string } {
  if (!input) return { match: false };
  try {
    if (type === "word" || type === "category") {
      const ok = input.toLowerCase().includes(pattern.toLowerCase());
      return { match: ok, matched: ok ? pattern : undefined };
    } else if (type === "regex") {
      const re = new RegExp(pattern, "i");
      const m = input.match(re);
      if (m) return { match: true, matched: m[0] };
      return { match: false };
    }
  } catch (e: any) {
    return { match: false, error: e.message };
  }
  return { match: false };
}

export default function ModerationPage() {
  const { lang } = useLang();
  const [rules, setRules] = useState<Rule[]>([]);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [stats, setStats] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [logsLoading, setLogsLoading] = useState(false);
  const [q, setQ] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [sevFilter, setSevFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [tab, setTab] = useState<"rules" | "logs">("rules");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>({ ...EMPTY_FORM });
  const [previewInput, setPreviewInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [delTarget, setDelTarget] = useState<Rule | null>(null);
  const [logUserFilter, setLogUserFilter] = useState("");
  const [logPage, setLogPage] = useState(0);
  const [logTotal, setLogTotal] = useState(0);

  async function loadRules() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (typeFilter) params.set("type", typeFilter);
      if (activeFilter) params.set("active", activeFilter);
      const qs = params.toString();
      const data = await api(`/api/moderation/rules${qs ? `?${qs}` : ""}`);
      setRules(data.rules || []);
    } catch (e: any) {
      toast.error(e.message || "Failed load rules");
    } finally {
      setLoading(false);
    }
  }
  async function loadStats() {
    try {
      const d = await api("/api/moderation/stats");
      setStats(d);
    } catch {}
  }
  async function loadLogs(page = 0) {
    setLogsLoading(true);
    try {
      const params = new URLSearchParams();
      if (logUserFilter.trim()) params.set("user_id", logUserFilter.trim());
      params.set("limit", "50");
      params.set("offset", String(page * 50));
      const data = await api(`/api/moderation/logs?${params.toString()}`);
      setLogs(data.logs || []);
      setLogTotal(data.total || 0);
    } catch (e: any) {
      toast.error(e.message || "Failed load logs");
    } finally {
      setLogsLoading(false);
    }
  }

  useEffect(() => {
    loadRules();
    loadStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const h = setTimeout(() => loadRules(), 300);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, typeFilter, sevFilter, activeFilter]);
  useEffect(() => {
    if (tab === "logs") loadLogs(logPage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, logPage]);

  const filteredRules = useMemo(() => {
    return rules.filter((r) => {
      if (sevFilter && r.severity !== sevFilter) return false;
      return true;
    });
  }, [rules, sevFilter]);

  function openNew() {
    setForm({ ...EMPTY_FORM });
    setPreviewInput("");
    setOpen(true);
  }
  function openEdit(r: Rule) {
    setForm({ id: r.id, pattern: r.pattern, type: r.type, severity: r.severity, is_active: r.is_active });
    setPreviewInput("");
    setOpen(true);
  }

  async function save() {
    if (!form.pattern?.trim() || form.pattern.trim().length < 1 || form.pattern.trim().length > 200) {
      toast.error(lang === "id" ? "Pattern 1-200 char wajib" : "Pattern 1-200 chars required");
      return;
    }
    if (form.type === "regex") {
      try {
        // eslint-disable-next-line no-new
        new RegExp(form.pattern, "i");
      } catch (e: any) {
        toast.error((lang === "id" ? "Regex invalid: " : "Invalid regex: ") + e.message);
        return;
      }
    }
    setSaving(true);
    try {
      if (form.id) {
        await api(`/api/moderation/rules/${form.id}`, {
          method: "PUT",
          body: JSON.stringify({
            pattern: form.pattern.trim(),
            type: form.type,
            severity: form.severity,
            is_active: form.is_active,
          }),
        });
        toast.success(lang === "id" ? "Rule diperbarui" : "Rule updated");
      } else {
        await api("/api/moderation/rules", {
          method: "POST",
          body: JSON.stringify({
            pattern: form.pattern.trim(),
            type: form.type,
            severity: form.severity,
            is_active: form.is_active,
          }),
        });
        toast.success(lang === "id" ? "Rule dibuat" : "Rule created");
      }
      setOpen(false);
      loadRules();
      loadStats();
    } catch (e: any) {
      toast.error(e.message || "Failed save");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(r: Rule) {
    try {
      await api(`/api/moderation/rules/${r.id}/toggle`, { method: "PATCH" });
      toast.success(r.is_active ? (lang === "id" ? "Dinonaktifkan" : "Deactivated") : (lang === "id" ? "Diaktifkan" : "Activated"));
      loadRules();
      loadStats();
    } catch (e: any) {
      toast.error(e.message);
    }
  }
  async function doDelete() {
    if (!delTarget) return;
    try {
      await api(`/api/moderation/rules/${delTarget.id}`, { method: "DELETE" });
      toast.success(lang === "id" ? "Rule dihapus" : "Rule deleted");
      setDelTarget(null);
      loadRules();
      loadStats();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  const previewResult = testPattern(form.pattern || "", form.type, previewInput);

  return (
    <div className="flex flex-col gap-4 w-full max-w-full overflow-hidden p-1">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 sm:h-6 sm:w-6" />
            {lang === "id" ? "Moderation Manager" : "Moderation Manager"}
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            {lang === "id" ? "Kelola blocklist kata, regex, kategori — realtime block & log." : "Manage blocklist words, regex, categories — realtime block & logs."}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => { loadRules(); loadStats(); if (tab==="logs") loadLogs(logPage); }} className="h-8 text-xs">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Reload
          </Button>
          <Button size="sm" onClick={openNew} className="h-8 text-xs">
            <Plus className="h-4 w-4" /> {lang==="id"?"Tambah Rule":"Add Rule"}
          </Button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground flex items-center gap-1"><Hash className="h-3 w-3"/>Total Rules</div><div className="text-xl font-bold mt-1">{stats.total_rules ?? "-"}</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground flex items-center gap-1"><Power className="h-3 w-3"/>Active</div><div className="text-xl font-bold mt-1">{stats.active_rules ?? "-"}</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground flex items-center gap-1"><Ban className="h-3 w-3"/>Blocks Today</div><div className="text-xl font-bold mt-1">{stats.blocks_today ?? 0}</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-xs text-muted-foreground flex items-center gap-1"><AlertTriangle className="h-3 w-3"/>High/Block</div><div className="text-xl font-bold mt-1">{stats.high_severity ?? 0}</div></CardContent></Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-full border bg-muted/30 p-1 w-fit">
        <button onClick={()=>setTab("rules")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${tab==="rules" ? "bg-card shadow border" : "text-muted-foreground hover:text-foreground"}`}>{lang==="id"?"Rules":"Rules"} ({filteredRules.length})</button>
        <button onClick={()=>setTab("logs")} className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${tab==="logs" ? "bg-card shadow border" : "text-muted-foreground hover:text-foreground"}`}>{lang==="id"?"Log Blokir":"Block Logs"} ({stats.logs_today ?? "?"})</button>
      </div>

      {tab==="rules" ? (
        <>
          {/* Search + filters */}
          <div className="flex flex-col md:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-10" placeholder={lang==="id"?"Cari pattern...":"Search pattern..."} value={q} onChange={(e)=>setQ(e.target.value)} />
            </div>
            <div className="flex gap-2 flex-wrap">
              <CustomSelect value={typeFilter} onChange={setTypeFilter} options={[{value:"",label:lang==="id"?"Semua Tipe":"All Types"}, ...TYPE_OPTIONS.map(o=>({value:o.value,label:o.value}))]} placeholder="Type" className="w-[130px]" />
              <CustomSelect value={sevFilter} onChange={setSevFilter} options={[{value:"",label:lang==="id"?"Semua Severity":"All Severity"}, {value:"low",label:"low"}, {value:"medium",label:"medium"}, {value:"high",label:"high"}, {value:"block",label:"block"}]} placeholder="Severity" className="w-[130px]" />
              <CustomSelect value={activeFilter} onChange={setActiveFilter} options={[{value:"",label:lang==="id"?"Semua Status":"All Status"}, {value:"true",label:"Active"}, {value:"false",label:"Inactive"}]} placeholder="Active" className="w-[120px]" />
            </div>
          </div>

          <Card>
            <CardHeader className="py-3"><CardTitle className="text-sm flex items-center gap-2"><ShieldAlert className="h-4 w-4"/>{lang==="id"?"Daftar Rule":"Rules List"} ({filteredRules.length})</CardTitle></CardHeader>
            <CardContent className="px-0 pt-0">
              {loading ? (
                <PageLoader label={lang==="id"?"Memuat...":"Loading..."} rows={3} />
              ) : filteredRules.length===0 ? (
                <div className="px-5 py-8 text-center text-sm text-muted-foreground">{lang==="id"?"Belum ada rule. Tambah untuk mulai filter prompt.":"No rules yet. Add one to start filtering."}</div>
              ) : (
                <div className="flex flex-col divide-y">
                  {filteredRules.map((r)=>(
                    <div key={r.id} className="flex flex-col sm:flex-row sm:items-center gap-2 px-4 md:px-5 py-3 hover:bg-muted/20">
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={r.severity==="block"||r.severity==="high" ? "destructive" : r.severity==="medium" ? "default" : "muted"}>{r.severity}</Badge>
                          <Badge variant="muted">{r.type}</Badge>
                          {!r.is_active && <Badge variant="destructive">inactive</Badge>}
                          <span className="text-xs text-muted-foreground">#{r.id}</span>
                        </div>
                        <div className="mt-1 font-mono text-sm break-all bg-muted/50 rounded px-2 py-1 border max-w-full overflow-x-auto">{r.pattern}</div>
                        <div className="text-[11px] text-muted-foreground mt-1 flex gap-2"><Calendar className="h-3 w-3"/> {new Date(r.created_at).toLocaleString(lang==="id"?"id-ID":"en-US")}</div>
                      </div>
                      <div className="flex gap-1 shrink-0 self-end sm:self-center">
                        <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={()=>toggleActive(r)} title={r.is_active?"Disable":"Enable"}><Power className={`h-4 w-4 ${r.is_active ? "text-emerald-500":"text-muted-foreground"}`} /></Button>
                        <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={()=>openEdit(r)}><Edit3 className="h-4 w-4" /></Button>
                        <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-destructive" onClick={()=>setDelTarget(r)}><Trash2 className="h-4 w-4" /></Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : (
        <>
          <div className="flex flex-col md:flex-row gap-2">
            <div className="relative flex-1 max-w-[240px]">
              <User className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-10" placeholder={lang==="id"?"Filter user_id...":"Filter user_id..."} value={logUserFilter} onChange={(e)=>setLogUserFilter(e.target.value)} onKeyDown={(e)=>{ if(e.key==="Enter"){ setLogPage(0); loadLogs(0);} }} />
            </div>
            <Button size="sm" variant="outline" onClick={()=>{ setLogPage(0); loadLogs(0); }} className="h-9 w-fit"><Search className="h-4 w-4" /> {lang==="id"?"Cari":"Search"}</Button>
            <div className="text-xs text-muted-foreground self-center">Total {logTotal} logs</div>
          </div>
          <Card>
            <CardContent className="px-0 pt-4">
              {logsLoading ? (
                <div className="px-5 py-8 text-center text-sm text-muted-foreground">Loading logs...</div>
              ) : logs.length===0 ? (
                <div className="px-5 py-8 text-center text-sm text-muted-foreground">{lang==="id"?"Belum ada log moderasi.":"No moderation logs yet."}</div>
              ) : (
                <div className="flex flex-col divide-y">
                  {logs.map((l)=>(
                    <div key={l.id} className="px-4 md:px-5 py-3">
                      <div className="flex flex-wrap gap-2 text-xs">
                        <Badge variant={l.action==="block" ? "destructive" : "muted"}>{l.action}</Badge>
                        <span className="text-muted-foreground flex items-center gap-1"><User className="h-3 w-3"/> {l.user_id}</span>
                        <span className="text-muted-foreground flex items-center gap-1"><Clock className="h-3 w-3"/> {new Date(l.created_at).toLocaleString(lang==="id"?"id-ID":"en-US")}</span>
                        {l.rule_id && <span className="text-muted-foreground">rule #{l.rule_id}</span>}
                      </div>
                      <div className="mt-1 text-xs"><span className="font-medium">Prompt:</span> <span className="break-all">{l.prompt?.slice(0,300)}</span></div>
                      <div className="mt-1 text-xs"><span className="font-medium">Matched:</span> <code className="bg-muted px-1 rounded">{l.matched_pattern}</code></div>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex justify-between items-center px-5 py-3 border-t">
                <Button variant="outline" size="sm" disabled={logPage===0} onClick={()=>{ setLogPage(p=>Math.max(0,p-1)); }}>Prev</Button>
                <span className="text-xs text-muted-foreground">Page {logPage+1} / {Math.max(1, Math.ceil(logTotal/50))}</span>
                <Button variant="outline" size="sm" disabled={(logPage+1)*50 >= logTotal} onClick={()=>{ setLogPage(p=>p+1); }}>Next</Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Add/Edit modal */}
      <Modal open={open} onClose={()=>setOpen(false)} title={form.id ? (lang==="id"?"Edit Rule":"Edit Rule") : (lang==="id"?"Tambah Rule":"Add Rule")}>
        <div className="flex flex-col gap-4">
          <Field label={lang==="id"?"Pattern (1-200 char)":"Pattern (1-200 chars)"}>
            <Textarea value={form.pattern} onChange={(e)=>setForm((f:any)=>({ ...f, pattern: e.target.value }))} placeholder={lang==="id"?"contoh: nsfw, (?:banned\\w+), politik":"e.g. nsfw, (?:banned\\w+), politics"} rows={3} maxLength={200} />
            <div className="text-[11px] text-muted-foreground mt-1">{form.pattern.length}/200</div>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type">
              <CustomSelect value={form.type} onChange={(v)=>setForm((f:any)=>({ ...f, type: v }))} options={TYPE_OPTIONS.map(o=>({value:o.value,label:o.label}))} />
            </Field>
            <Field label="Severity">
              <CustomSelect value={form.severity} onChange={(v)=>setForm((f:any)=>({ ...f, severity: v }))} options={SEV_OPTIONS.map(o=>({value:o.value,label:o.label}))} />
            </Field>
          </div>
          <Field label="Active">
            <div className="flex items-center gap-2"><Switch checked={form.is_active} onCheckedChange={(v:boolean)=>setForm((f:any)=>({ ...f, is_active: v }))} /><span className="text-xs">{form.is_active ? "Active" : "Inactive"}</span></div>
          </Field>
          {/* Preview live */}
          <div className="rounded border bg-muted/30 p-3 flex flex-col gap-2">
            <div className="text-xs font-medium flex items-center gap-1"><Eye className="h-3 w-3"/>{lang==="id"?"Preview Test (live)":"Preview Test (live)"}</div>
            <Input value={previewInput} onChange={(e)=>setPreviewInput(e.target.value)} placeholder={lang==="id"?"Ketik prompt untuk test rule...":"Type prompt to test rule..."} />
            <div className={`text-xs rounded px-2 py-1 ${previewResult.error ? "bg-destructive/10 text-destructive" : previewResult.match ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20" : "bg-muted"}`}>
              {previewResult.error ? `Error: ${previewResult.error}` : previewResult.match ? `${lang==="id"?"Cocok":"Matched"}: ${previewResult.matched || form.pattern}` : lang==="id"?"Tidak cocok":"No match"}
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={()=>setOpen(false)}>{lang==="id"?"Batal":"Cancel"}</Button>
            <Button onClick={save} disabled={saving}>{saving ? (lang==="id"?"Menyimpan...":"Saving...") : (lang==="id"?"Simpan":"Save")}</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog open={!!delTarget} onClose={()=>setDelTarget(null)} title={lang==="id"?"Hapus Rule?":"Delete Rule?"} description={delTarget ? `${lang==="id"?"Yakin hapus rule":"Delete rule"} "${delTarget.pattern.slice(0,50)}"?` : ""} onConfirm={doDelete} confirmLabel={lang==="id"?"Ya, Hapus":"Yes, Delete"} variant="destructive" />
    </div>
  );
}
