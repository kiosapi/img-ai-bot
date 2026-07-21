"use client";
import { useEffect, useState } from "react";
import { Power, Command, ToggleLeft, ShieldAlert, Users, Image as ImageIcon, Gift, Sparkles, Layers, Settings2, Crown, Wallet, Bot, Search, RefreshCw, CheckCircle2, XCircle } from "lucide-react";
import { PageLoader } from "@/components/ui/page-loader";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";
import { toast } from "sonner";

interface Cmd { name: string; is_enabled: boolean; group: string; icon: string; label: string; description: string; is_core: boolean; label_id: string; desc_id: string; desc_en: string; }

const GROUP_ICON: Record<string, any> = { core: Command, premium: Crown, social: Users, generation: ImageIcon, feature: Sparkles };
const CMD_ICON_MAP: Record<string, any> = { myworks: Layers, batch: Layers, checkin: Gift, referral: Users, sticker: ImageIcon, enhance: Sparkles, model: Bot, premium: Crown, balance: Wallet, generate: ImageIcon, edit: Settings2, style: Sparkles, lang: Command, size: Command, quota: Command, batchold: Layers };

function Toggle({ enabled, onToggle, disabled }: { enabled: boolean; onToggle: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button disabled={disabled} onClick={() => !disabled && onToggle(!enabled)} className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${disabled ? "opacity-50 cursor-not-allowed" : ""} ${enabled ? "bg-emerald-500" : "bg-muted"}`}>
      <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform ${enabled ? "translate-x-5" : "translate-x-0"}`} />
    </button>
  );
}

export default function CommandsPage() {
  const { lang } = useLang();
  const [cmds, setCmds] = useState<Cmd[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [groupFilter, setGroupFilter] = useState<string>("all");
  const [confirmCmd, setConfirmCmd] = useState<Cmd | null>(null);
  const [pendingVal, setPendingVal] = useState<boolean>(false);
  const [saving, setSaving] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try { const d = await api("/api/commands") as any; setCmds(d.commands || []); } catch (e: any) { toast.error(e.message); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  const groups = Array.from(new Set(cmds.map(c => c.group))).sort();
  const filtered = cmds.filter(c => {
    if (groupFilter !== "all" && c.group !== groupFilter) return false;
    if (q && !`${c.name} ${c.label} ${c.description}`.toLowerCase().includes(q.toLowerCase())) return false;
    return true;
  });

  async function doToggle(cmd: Cmd, enabled: boolean) {
    if (cmd.is_core && !enabled) { setConfirmCmd(cmd); setPendingVal(enabled); return; }
    await execToggle(cmd, enabled);
  }
  async function execToggle(cmd: Cmd, enabled: boolean) {
    setSaving(cmd.name);
    try {
      await api(`/api/commands/${cmd.name}/toggle`, { method: "PUT", body: JSON.stringify({ enabled }) });
      setCmds(prev => prev.map(c => c.name === cmd.name ? { ...c, is_enabled: enabled } : c));
      toast.success(`${cmd.name} ${enabled ? (lang === "id" ? "diaktifkan" : "enabled") : (lang === "id" ? "dimatikan" : "disabled")}`);
    } catch (e: any) { toast.error(e.message); } finally { setSaving(null); setConfirmCmd(null); }
  }

  if (loading && !cmds.length) return <PageLoader label={lang === "id" ? "Memuat..." : "Loading..."} cards={3} rows={4} />;

  return (
    <div className="flex flex-col gap-4 w-full max-w-full min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0"><h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2"><Command className="h-5 w-5 sm:h-6 sm:w-6" />{lang === "id" ? "Command Manager" : "Command Manager"}</h1><p className="text-xs sm:text-sm text-muted-foreground mt-1">{lang === "id" ? "Aktifkan / matikan command bot tanpa edit code — langsung efek instan." : "Toggle bot commands on/off without code — instant effect."}</p></div>
        <Button variant="outline" size="sm" onClick={load} className="h-8 text-xs shrink-0"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Reload</Button>
      </div>

      <div className="flex flex-wrap gap-2">
        <div className="flex gap-1 rounded-full border bg-muted/30 p-0.5 overflow-x-auto scrollbar-none">
          <button onClick={() => setGroupFilter("all")} className={`rounded-full px-3 py-1 text-xs font-medium shrink-0 transition ${groupFilter === "all" ? "bg-card shadow border" : "text-muted-foreground"}`}>All ({cmds.length})</button>
          {groups.map(g => { const Icon = GROUP_ICON[g] || Command; const count = cmds.filter(c => c.group === g).length; return (<button key={g} onClick={() => setGroupFilter(g)} className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium shrink-0 transition ${groupFilter === g ? "bg-card shadow border" : "text-muted-foreground"}`}> <Icon className="h-3 w-3" />{g} ({count})</button>); })}
        </div>
        <div className="relative"><Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" /><input value={q} onChange={e => setQ(e.target.value)} placeholder={lang === "id" ? "Cari command..." : "Search command..."} className="h-8 w-[180px] sm:w-[220px] rounded-full border bg-background pl-8 pr-3 text-xs outline-none focus:ring-1" /></div>
      </div>

      <div className="grid gap-3 grid-cols-1 md:grid-cols-2 w-full">
        {filtered.map(cmd => {
          const Icon = CMD_ICON_MAP[cmd.name] || Command;
          const isOn = cmd.is_enabled;
          return (
            <Card key={cmd.name} className={`w-full overflow-hidden transition-all ${!isOn ? "opacity-60 bg-muted/20" : ""} ${cmd.is_core ? "border-primary/20" : ""}`}>
              <CardContent className="p-3 sm:p-4 flex items-start gap-3">
                <div className={`mt-0.5 flex h-8 w-8 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-lg ${isOn ? "bg-emerald-500/15 text-emerald-600" : "bg-muted text-muted-foreground"}`}><Icon className="h-4 w-4 sm:h-5 sm:w-5" /></div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5"><span className="font-medium text-sm">/{cmd.name}</span>{cmd.is_core && <Badge variant="default" className="text-[9px] px-1.5 py-0">CORE</Badge>}<Badge variant={isOn ? "muted" : "destructive"} className="text-[10px] flex items-center gap-1">{isOn ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{isOn ? "ON" : "OFF"}</Badge><Badge variant="muted" className="text-[10px]">{cmd.group}</Badge></div>
                  <div className="mt-1 text-xs text-muted-foreground leading-snug line-clamp-2">{lang === "id" ? (cmd.desc_id || cmd.description) : (cmd.desc_en || cmd.description)}</div>
                </div>
                <div className="shrink-0 ml-1 flex flex-col items-center gap-1"><Toggle enabled={isOn} disabled={saving === cmd.name} onToggle={(v) => doToggle(cmd, v)} />{saving === cmd.name && <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>
      {filtered.length === 0 && <div className="py-12 text-center text-sm text-muted-foreground">{lang === "id" ? "Tidak ada command cocok" : "No matching commands"}</div>}

      <ConfirmDialog open={!!confirmCmd} onClose={() => setConfirmCmd(null)} title={lang === "id" ? "Matikan core command?" : "Disable core command?"} description={`${confirmCmd?.name ? `/${confirmCmd.name}` : ""} ${lang === "id" ? "adalah command inti — user akan tidak bisa pakai sampai diaktifkan lagi. Lanjut?" : "is a core command — users cannot use it until re-enabled. Continue?"}`} confirmLabel={lang === "id" ? "Ya, Matikan" : "Yes, Disable"} variant="destructive" loading={saving !== null} onConfirm={() => confirmCmd && execToggle(confirmCmd, pendingVal)} />

      <div className="rounded-lg border border-dashed p-2.5 sm:p-3 text-[11px] sm:text-xs text-muted-foreground flex items-start gap-2"><Power className="h-3.5 w-3.5 shrink-0 mt-0.5" /><span>{lang === "id" ? "Perubahan langsung live — bot cek feat_command_{name}_enabled di settings tiap request, no redeploy. Core commands ada badge CORE, toggle butuh konfirmasi." : "Changes live instantly — bot checks feat_command_{name}_enabled in settings each request, no redeploy. Core badges need confirm."}</span></div>
    </div>
  );
}
