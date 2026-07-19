"use client";
import { useEffect, useState, useCallback } from "react";
import { Crown, Clock, DollarSign, CheckCircle2, XCircle, Image as ImageIcon, ExternalLink, CreditCard, BarChart3, Hourglass, StickyNote } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, Textarea } from "@/components/ui/controls";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

const TABS = [
  { v: "pending", label: "Menunggu" },
  { v: "approved", label: "Disetujui" },
  { v: "rejected", label: "Ditolak" },
];
const rupiah = (n: number) => "Rp" + Number(n).toLocaleString("id-ID");

export default function OrdersPage() {
  const [tab, setTab] = useState("pending");
  const [data, setData] = useState<any>({ orders: [], counts: {} });
  const [stats, setStats] = useState<any>(null);
  const [proof, setProof] = useState<number | null>(null);
  const [rejectId, setRejectId] = useState<number | null>(null);
  const [approveId, setApproveId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api(`/api/orders?status=${tab}`).then(setData).catch(() => {});
    api("/api/premium/stats").then(setStats).catch(() => {});
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  async function approve(id: number) {
    setBusy(true);
    try { await api(`/api/orders/${id}/approve`, { method: "POST" }); toast.success("Disetujui! Premium aktif & user diberi tahu."); setApproveId(null); load(); }
    catch (e: any) { toast.error(e.message || "Gagal"); } finally { setBusy(false); }
  }

  async function doReject() {
    if (rejectId == null) return;
    setBusy(true);
    try {
      await api(`/api/orders/${rejectId}/reject`, { method: "POST", body: JSON.stringify({ note: note.trim() || null }) });
      toast.success("Ditolak & user diberi tahu."); setRejectId(null); setNote(""); load();
    } catch (e: any) { toast.error(e.message || "Gagal"); } finally { setBusy(false); }
  }

  const badge = (s: string) => s === "approved" ? <Badge variant="success">disetujui</Badge> : s === "rejected" ? <Badge variant="destructive">ditolak</Badge> : <Badge variant="default">menunggu</Badge>;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Pesanan Premium</h1>
        <p className="text-sm text-muted-foreground">Verifikasi pembayaran & aktivasi</p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Card><CardContent className="pt-5"><Crown className="h-5 w-5 text-amber-500" /><div className="mt-2 text-2xl font-extrabold">{stats.active_premium}</div><div className="text-xs text-muted-foreground">Premium Aktif</div></CardContent></Card>
          <Card><CardContent className="pt-5"><Clock className="h-5 w-5 text-primary" /><div className="mt-2 text-2xl font-extrabold">{stats.pending_orders}</div><div className="text-xs text-muted-foreground">Menunggu</div></CardContent></Card>
          <Card><CardContent className="pt-5"><CheckCircle2 className="h-5 w-5 text-emerald-500" /><div className="mt-2 text-2xl font-extrabold">{stats.total_approved}</div><div className="text-xs text-muted-foreground">Total Approved</div></CardContent></Card>
          <Card><CardContent className="pt-5"><DollarSign className="h-5 w-5 text-emerald-500" /><div className="mt-2 text-xl font-extrabold">{rupiah(stats.total_revenue)}</div><div className="text-xs text-muted-foreground">Total Pendapatan</div></CardContent></Card>
        </div>
      )}

      <div className="flex gap-2">
        {TABS.map((t) => (
          <button key={t.v} onClick={() => setTab(t.v)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${tab === t.v ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
            {t.label}{data.counts[t.v] ? ` (${data.counts[t.v]})` : ""}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3">
        {data.orders.map((o: any) => (
          <Card key={o.id}>
            <CardContent className="pt-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-bold">#{o.id}</span>
                    <span className="text-sm">{o.username ? "@" + o.username : o.first_name || o.user_id}</span>
                    {badge(o.status)}
                  </div>
                  <div className="mt-2 flex flex-col gap-0.5 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1"><Crown className="h-3.5 w-3.5" /> {o.plan_name} · <span className="font-semibold text-foreground">{rupiah(o.amount)}</span></span>
                    <span className="flex items-center gap-1 flex-wrap">
                      <CreditCard className="h-3.5 w-3.5" /> {o.method_name}
                      <span className="mx-0.5">·</span>
                      <BarChart3 className="h-3.5 w-3.5" /> {o.daily_limit === 0 ? "Unlimited" : o.daily_limit + "/hari"}
                      <span className="mx-0.5">·</span>
                      <Hourglass className="h-3.5 w-3.5" /> {o.duration_days}h
                    </span>
                    <span className="text-xs">{new Date(o.created_at).toLocaleString("id-ID")}</span>
                    {o.note && <span className="flex items-center gap-1 text-xs italic"><StickyNote className="h-3 w-3" /> {o.note}</span>}
                  </div>
                </div>
                {o.proof_file_id
                  ? <Button size="sm" variant="outline" onClick={() => setProof(o.id)}><ImageIcon className="h-4 w-4" />Bukti</Button>
                  : <Badge variant="muted">no bukti</Badge>}
              </div>
              {o.status === "pending" && (
                <div className="mt-4 flex gap-2">
                  <Button size="sm" variant="success" className="flex-1" onClick={() => setApproveId(o.id)} disabled={busy}><CheckCircle2 className="h-4 w-4" />Setujui</Button>
                  <Button size="sm" variant="destructive" className="flex-1" onClick={() => { setRejectId(o.id); setNote(""); }} disabled={busy}><XCircle className="h-4 w-4" />Tolak</Button>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
        {data.orders.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground">Tidak ada pesanan {TABS.find(t => t.v === tab)?.label.toLowerCase()}.</div>}
      </div>

      {/* Proof viewer */}
      <Modal open={proof != null} onClose={() => setProof(null)} title="Bukti Pembayaran">
        {proof != null && (
          <div className="flex flex-col gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/orders/${proof}/proof`} alt="Bukti pembayaran" className="w-full rounded-lg border" />
            <a href={`/api/orders/${proof}/proof`} target="_blank" rel="noreferrer">
              <Button variant="outline" className="w-full"><ExternalLink className="h-4 w-4" />Buka di tab baru</Button>
            </a>
          </div>
        )}
      </Modal>

      {/* Reject dialog */}
      <Modal open={rejectId != null} onClose={() => setRejectId(null)} title="Tolak Pembayaran">
        <p className="mb-3 text-sm text-muted-foreground">Alasan penolakan (opsional, dikirim ke user):</p>
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="mis. Nominal tidak sesuai / bukti tidak valid" className="mb-4" />
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={() => setRejectId(null)}>Batal</Button>
          <Button variant="destructive" className="flex-1" onClick={doReject} disabled={busy}>{busy ? "..." : "Tolak"}</Button>
        </div>
      </Modal>

      {/* Approve confirm */}
      <ConfirmDialog
        open={approveId != null}
        onClose={() => setApproveId(null)}
        onConfirm={() => approveId != null && approve(approveId)}
        loading={busy}
        title="Setujui Pembayaran"
        variant="success"
        confirmLabel="Ya, Setujui"
        description="Setujui pembayaran ini? Premium user akan langsung aktif dan mereka akan diberi tahu lewat bot."
      />
    </div>
  );
}
