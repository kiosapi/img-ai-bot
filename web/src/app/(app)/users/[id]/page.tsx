"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, XCircle, ImageIcon, Ban, Wallet, Plus, Minus, History } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, Input, Textarea } from "@/components/ui/controls";
import { Modal } from "@/components/ui/modal";
import { useLang } from "@/lib/i18n";

export default function UserDetail() {
  const params = useParams();
  const id = (params as any)?.id as string | string[];
  const uidStr = Array.isArray(id) ? id[0] : id;
  const router = useRouter();
  const { t, lang } = useLang();
  const rupiah = (n: number) => "Rp" + Number(n || 0).toLocaleString("id-ID");
  const [data, setData] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustMode, setAdjustMode] = useState<"add" | "deduct">("add");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [errMsg, setErrMsg] = useState("");

  const load = () => {
    if (!uidStr) return;
    setErrMsg("");
    api(`/api/users/${encodeURIComponent(uidStr)}`)
      .then(setData)
      .catch((e: any) => { const msg = e?.message || t("users.user_not_found"); setErrMsg(msg); toast.error(msg); });
  };
  useEffect(() => { load(); }, [uidStr]);

  async function toggleBan() {
    try {
      await api("/api/users/ban", { method: "POST", body: JSON.stringify({ user_id: Number(uidStr), banned: !data.user.is_banned }) });
      toast.success(data.user.is_banned ? t("users.unban") : t("users.ban"));
      setData((d: any) => ({ ...d, user: { ...d.user, is_banned: !d.user.is_banned } }));
    } catch { toast.error(t("settings.failed")); }
  }

  function openAdjust(mode: "add" | "deduct") { setAdjustMode(mode); setAmount(""); setReason(""); setAdjustOpen(true); }

  async function submitAdjust() {
    const v = Number(amount.replace(/\D/g, ""));
    if (!v || v <= 0) { toast.error(lang === "id" ? "Nominal tidak valid" : "Invalid amount"); return; }
    setBusy(true);
    try {
      const delta = adjustMode === "add" ? v : -v;
      await api("/api/users/balance/adjust", { method: "POST", body: JSON.stringify({ user_id: Number(uidStr), delta, reason: reason.trim() || (lang==="id"?"Penyesuaian manual admin":"Manual admin adjustment") }) });
      toast.success(t("users.balance_changed", { mode: adjustMode === "add" ? t("users.add_balance") : t("users.deduct_balance") }));
      setAdjustOpen(false); load();
    } catch (e: any) { toast.error(e.message || t("settings.failed")); } finally { setBusy(false); }
  }

  async function openHistory() {
    try { const r = await api(`/api/users/${uidStr}/balance/logs`); setLogs(r.logs || []); setHistoryOpen(true); }
    catch { toast.error(t("settings.failed")); }
  }

  if (errMsg) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <Link href="/users" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground w-fit"><ArrowLeft className="h-4 w-4" />{lang==="id"?"Kembali":"Back"}</Link>
        <Card><CardContent className="py-10 text-center"><div className="text-sm font-medium">{errMsg}</div><div className="text-xs text-muted-foreground mt-2">ID: {uidStr}</div><Button className="mt-4" onClick={() => router.push("/users")}>{lang==="id"?"Ke daftar user":"To user list"}</Button></CardContent></Card>
      </div>
    );
  }

  if (!data) return <div className="py-20 text-center text-muted-foreground">{t("common.loading")} user {uidStr}...</div>;
  const u = data.user;

  return (
    <div className="flex flex-col gap-4 md:gap-5 p-1">
      <Link href="/users" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground w-fit"><ArrowLeft className="h-4 w-4" />{lang==="id"?"Kembali ke daftar user":"Back to users"}</Link>

      <Card>
        <CardContent className="pt-5">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-2xl font-bold text-white">{(u.username || u.first_name || "U")[0].toUpperCase()}</div>
            <div className="min-w-0 flex-1">
              <div className="text-xl font-bold truncate">{u.username ? "@" + u.username : (u.first_name || "User")}{u.is_banned && <Badge variant="destructive" className="ml-2">{t("users.banned")}</Badge>}</div>
              <div className="text-sm text-muted-foreground break-all">ID {u.user_id}</div>
              {u.first_name && <div className="text-sm text-muted-foreground truncate">{u.first_name}</div>}
            </div>
            <Button size="sm" variant={u.is_banned ? "success" : "destructive"} onClick={toggleBan} className="w-full sm:w-auto">{u.is_banned ? <><CheckCircle2 className="h-4 w-4" />{t("users.unban")}</> : <><Ban className="h-4 w-4" />{t("users.ban")}</>}</Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold">{data.total}</div><div className="text-xs text-muted-foreground mt-1">{t("users.total_images")}</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-emerald-500">{data.success}</div><div className="text-xs text-muted-foreground mt-1">Success</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-destructive">{data.failed}</div><div className="text-xs text-muted-foreground mt-1">Failed</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-amber-500">{data.today}</div><div className="text-xs text-muted-foreground mt-1">{lang==="id"?"Hari Ini":"Today"}</div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><Wallet className="h-4 w-4" />{t("users.balance")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div><div className="text-2xl font-extrabold">{rupiah(u.balance)}</div><div className="text-xs text-muted-foreground">{lang==="id"?"Bahasa":"Language"}: {u.lang === "en" ? "English" : "Indonesia"}</div></div>
            <Button size="sm" variant="outline" onClick={openHistory}><History className="h-4 w-4" />{t("users.balance_history")}</Button>
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <Button size="sm" variant="success" className="flex-1" onClick={() => openAdjust("add")}><Plus className="h-4 w-4" />{t("users.add_balance")}</Button>
            <Button size="sm" variant="destructive" className="flex-1" onClick={() => openAdjust("deduct")}><Minus className="h-4 w-4" />{t("users.deduct_balance")}</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><ImageIcon className="h-4 w-4" />{t("users.gen_history")} ({data.generations.length})</CardTitle></CardHeader>
        <CardContent className="px-0 pt-0">
          {data.generations.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">{t("analytics.no_data")}</div>}
          {data.generations.map((g: any, i: number) => (
            <div key={i} className="flex items-start gap-3 border-b px-4 md:px-5 py-3 last:border-0">
              <Badge variant={g.kind === "edit" ? "default" : "muted"} className="mt-0.5 shrink-0">{g.kind}</Badge>
              <div className="min-w-0 flex-1"><div className="text-sm break-words">{g.prompt || <span className="text-muted-foreground italic">{t("errors.no_prompt")}</span>}</div><div className="text-xs text-muted-foreground mt-0.5 break-all">{g.size} - {new Date(g.created_at).toLocaleString(lang==="id"?"id-ID":"en-US")}</div></div>
              {g.success ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" /> : <XCircle className="h-4 w-4 shrink-0 text-destructive mt-0.5" />}
            </div>
          ))}
        </CardContent>
      </Card>

      <Modal open={adjustOpen} onClose={() => setAdjustOpen(false)} title={adjustMode === "add" ? t("users.add_balance") : t("users.deduct_balance")}>
        <div className="flex flex-col gap-3">
          <div><label className="mb-1.5 block text-sm font-medium">{t("users.amount")}</label><Input type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="50000" /></div>
          <div><label className="mb-1.5 block text-sm font-medium">{t("users.note")}</label><Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("users.note_ph")} /></div>
          <Button variant={adjustMode === "add" ? "success" : "destructive"} onClick={submitAdjust} disabled={busy}>{busy ? t("users.saving") : adjustMode === "add" ? t("users.add_balance") : t("users.deduct_balance")}</Button>
        </div>
      </Modal>

      <Modal open={historyOpen} onClose={() => setHistoryOpen(false)} title={t("users.balance_history_title")}>
        <div className="flex flex-col gap-2">
          {logs.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">{t("common.no_data")}</div>}
          {logs.map((l) => (
            <div key={l.id} className="flex items-center justify-between border-b pb-2 last:border-0">
              <div><div className="text-sm font-medium">{l.reason || "-"}</div><div className="text-xs text-muted-foreground">{new Date(l.created_at).toLocaleString(lang==="id"?"id-ID":"en-US")}</div></div>
              <div className="text-right"><div className={`text-sm font-bold ${l.delta >= 0 ? "text-emerald-500" : "text-destructive"}`}>{l.delta >= 0 ? "+" : ""}{rupiah(l.delta)}</div><div className="text-xs text-muted-foreground">{lang==="id"?"saldo":"balance"}: {rupiah(l.balance_after)}</div></div>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
