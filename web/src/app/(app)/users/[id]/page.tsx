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

const rupiah = (n: number) => "Rp" + Number(n || 0).toLocaleString("id-ID");

export default function UserDetail() {
  const { id } = useParams();
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustMode, setAdjustMode] = useState<"add" | "deduct">("add");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const load = () => {
    api(`/api/users/${id}`).then(setData).catch(() => { toast.error("User tidak ditemukan"); router.push("/users"); });
  };
  useEffect(() => { load(); }, [id, router]);

  async function toggleBan() {
    try {
      await api("/api/users/ban", { method: "POST", body: JSON.stringify({ user_id: Number(id), banned: !data.user.is_banned }) });
      toast.success(data.user.is_banned ? "User di-unban" : "User dibanned");
      setData((d: any) => ({ ...d, user: { ...d.user, is_banned: !d.user.is_banned } }));
    } catch { toast.error("Gagal"); }
  }

  function openAdjust(mode: "add" | "deduct") {
    setAdjustMode(mode); setAmount(""); setReason(""); setAdjustOpen(true);
  }

  async function submitAdjust() {
    const v = Number(amount.replace(/\D/g, ""));
    if (!v || v <= 0) { toast.error("Nominal tidak valid"); return; }
    setBusy(true);
    try {
      const delta = adjustMode === "add" ? v : -v;
      await api("/api/users/balance/adjust", {
        method: "POST",
        body: JSON.stringify({ user_id: Number(id), delta, reason: reason.trim() || "Penyesuaian manual admin" }),
      });
      toast.success(adjustMode === "add" ? "Saldo berhasil ditambahkan" : "Saldo berhasil dikurangi");
      setAdjustOpen(false);
      load();
    } catch (e: any) { toast.error(e.message || "Gagal menyesuaikan saldo"); }
    finally { setBusy(false); }
  }

  async function openHistory() {
    try {
      const r = await api(`/api/users/${id}/balance/logs`);
      setLogs(r.logs || []);
      setHistoryOpen(true);
    } catch { toast.error("Gagal memuat riwayat"); }
  }

  if (!data) return <div className="py-20 text-center text-muted-foreground">Memuat...</div>;
  const u = data.user;

  return (
    <div className="flex flex-col gap-5">
      <Link href="/users" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground w-fit">
        <ArrowLeft className="h-4 w-4" />Kembali ke daftar user
      </Link>

      <Card>
        <CardContent className="pt-5">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-2xl font-bold text-white">
              {(u.username || u.first_name || "U")[0].toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xl font-bold truncate">
                {u.username ? "@" + u.username : (u.first_name || "User")}
                {u.is_banned && <Badge variant="destructive" className="ml-2">banned</Badge>}
              </div>
              <div className="text-sm text-muted-foreground">ID {u.user_id}</div>
              {u.first_name && <div className="text-sm text-muted-foreground">{u.first_name}</div>}
            </div>
            <Button size="sm" variant={u.is_banned ? "success" : "destructive"} onClick={toggleBan}>
              {u.is_banned ? <><CheckCircle2 className="h-4 w-4" />Unban</> : <><Ban className="h-4 w-4" />Ban</>}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold">{data.total}</div><div className="text-xs text-muted-foreground mt-1">Total Gambar</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-emerald-500">{data.success}</div><div className="text-xs text-muted-foreground mt-1">Berhasil</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-destructive">{data.failed}</div><div className="text-xs text-muted-foreground mt-1">Gagal</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-amber-500">{data.today}</div><div className="text-xs text-muted-foreground mt-1">Hari Ini</div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle><Wallet className="h-4 w-4" />Saldo Akun</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-extrabold">{rupiah(u.balance)}</div>
              <div className="text-xs text-muted-foreground">Bahasa: {u.lang === "en" ? "English" : "Indonesia"}</div>
            </div>
            <Button size="sm" variant="outline" onClick={openHistory}><History className="h-4 w-4" />Riwayat</Button>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="success" className="flex-1" onClick={() => openAdjust("add")}><Plus className="h-4 w-4" />Tambah Saldo</Button>
            <Button size="sm" variant="destructive" className="flex-1" onClick={() => openAdjust("deduct")}><Minus className="h-4 w-4" />Kurangi Saldo</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><ImageIcon className="h-4 w-4" />Riwayat Generate ({data.generations.length})</CardTitle></CardHeader>
        <CardContent className="px-0 pt-0">
          {data.generations.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">Belum ada aktivitas</div>}
          {data.generations.map((g: any, i: number) => (
            <div key={i} className="flex items-start gap-3 border-b px-5 py-3 last:border-0">
              <Badge variant={g.kind === "edit" ? "default" : "muted"} className="mt-0.5 shrink-0">{g.kind}</Badge>
              <div className="min-w-0 flex-1">
                <div className="text-sm break-words">{g.prompt || <span className="text-muted-foreground italic">tanpa prompt</span>}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{g.size} · {new Date(g.created_at).toLocaleString("id-ID")}</div>
              </div>
              {g.success
                ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                : <XCircle className="h-4 w-4 shrink-0 text-destructive mt-0.5" />}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Adjust balance modal */}
      <Modal open={adjustOpen} onClose={() => setAdjustOpen(false)} title={adjustMode === "add" ? "Tambah Saldo" : "Kurangi Saldo"}>
        <div className="flex flex-col gap-3">
          <div>
            <label className="mb-1.5 block text-sm font-medium">Nominal</label>
            <Input type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="mis. 50000" />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">Catatan (opsional, dikirim ke user)</label>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="mis. Kompensasi gangguan bot" />
          </div>
          <Button variant={adjustMode === "add" ? "success" : "destructive"} onClick={submitAdjust} disabled={busy}>
            {busy ? "Menyimpan..." : adjustMode === "add" ? "Tambah Saldo" : "Kurangi Saldo"}
          </Button>
        </div>
      </Modal>

      {/* Balance history modal */}
      <Modal open={historyOpen} onClose={() => setHistoryOpen(false)} title="Riwayat Perubahan Saldo">
        <div className="flex flex-col gap-2">
          {logs.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">Belum ada riwayat</div>}
          {logs.map((l) => (
            <div key={l.id} className="flex items-center justify-between border-b pb-2 last:border-0">
              <div>
                <div className="text-sm font-medium">{l.reason || "-"}</div>
                <div className="text-xs text-muted-foreground">{new Date(l.created_at).toLocaleString("id-ID")}</div>
              </div>
              <div className="text-right">
                <div className={`text-sm font-bold ${l.delta >= 0 ? "text-emerald-500" : "text-destructive"}`}>
                  {l.delta >= 0 ? "+" : ""}{rupiah(l.delta)}
                </div>
                <div className="text-xs text-muted-foreground">saldo: {rupiah(l.balance_after)}</div>
              </div>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
