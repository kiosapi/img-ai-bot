"use client";
import { useEffect, useState, useCallback } from "react";
import { Wallet, Clock, DollarSign, CheckCircle2, XCircle, Image as ImageIcon, ExternalLink, CreditCard, StickyNote } from "lucide-react";
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

export default function DepositsPage() {
  const [tab, setTab] = useState("pending");
  const [data, setData] = useState<any>({ deposits: [], counts: {} });
  const [stats, setStats] = useState<any>(null);
  const [proof, setProof] = useState<number | null>(null);
  const [rejectId, setRejectId] = useState<number | null>(null);
  const [approveId, setApproveId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api(`/api/deposits?status=${tab}`).then(setData).catch(() => {});
    api("/api/deposits/stats").then(setStats).catch(() => {});
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  async function approve(id: number) {
    setBusy(true);
    try { await api(`/api/deposits/${id}/approve`, { method: "POST" }); toast.success("Disetujui! Saldo user bertambah otomatis."); setApproveId(null); load(); }
    catch (e: any) { toast.error(e.message || "Gagal"); } finally { setBusy(false); }
  }

  async function doReject() {
    if (rejectId == null) return;
    setBusy(true);
    try {
      await api(`/api/deposits/${rejectId}/reject`, { method: "POST", body: JSON.stringify({ note: note.trim() || null }) });
      toast.success("Ditolak & user diberi tahu."); setRejectId(null); setNote(""); load();
    } catch (e: any) { toast.error(e.message || "Gagal"); } finally { setBusy(false); }
  }

  const badge = (s: string) => s === "approved" ? <Badge variant="success">disetujui</Badge> : s === "rejected" ? <Badge variant="destructive">ditolak</Badge> : <Badge variant="default">menunggu</Badge>;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Deposit Saldo</h1>
        <p className="text-sm text-muted-foreground">Verifikasi top up saldo user</p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Card><CardContent className="pt-5"><Clock className="h-5 w-5 text-primary" /><div className="mt-2 text-2xl font-extrabold">{stats.pending_deposits}</div><div className="text-xs text-muted-foreground">Menunggu</div></CardContent></Card>
          <Card><CardContent className="pt-5"><CheckCircle2 className="h-5 w-5 text-emerald-500" /><div className="mt-2 text-2xl font-extrabold">{stats.total_approved}</div><div className="text-xs text-muted-foreground">Total Approved</div></CardContent></Card>
          <Card><CardContent className="pt-5"><DollarSign className="h-5 w-5 text-emerald-500" /><div className="mt-2 text-xl font-extrabold">{rupiah(stats.total_deposited)}</div><div className="text-xs text-muted-foreground">Total Masuk</div></CardContent></Card>
          <Card><CardContent className="pt-5"><Wallet className="h-5 w-5 text-amber-500" /><div className="mt-2 text-xl font-extrabold">{rupiah(stats.total_balance_outstanding)}</div><div className="text-xs text-muted-foreground">Total Saldo Beredar</div></CardContent></Card>
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
        {data.deposits.map((d: any) => (
          <Card key={d.id}>
            <CardContent className="pt-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-bold">#{d.id}</span>
                    <span className="text-sm">{d.username ? "@" + d.username : d.first_name || d.user_id}</span>
                    {badge(d.status)}
                  </div>
                  <div className="mt-2 flex flex-col gap-0.5 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1"><Wallet className="h-3.5 w-3.5" /> <span className="font-semibold text-foreground">{rupiah(d.amount)}</span></span>
                    <span className="flex items-center gap-1"><CreditCard className="h-3.5 w-3.5" /> {d.method_name}</span>
                    <span className="text-xs">{new Date(d.created_at).toLocaleString("id-ID")}</span>
                    {d.note && <span className="flex items-center gap-1 text-xs italic"><StickyNote className="h-3 w-3" /> {d.note}</span>}
                  </div>
                </div>
                {d.proof_file_id
                  ? <Button size="sm" variant="outline" onClick={() => setProof(d.id)}><ImageIcon className="h-4 w-4" />Bukti</Button>
                  : <Badge variant="muted">no bukti</Badge>}
              </div>
              {d.status === "pending" && (
                <div className="mt-4 flex gap-2">
                  <Button size="sm" variant="success" className="flex-1" onClick={() => setApproveId(d.id)} disabled={busy}><CheckCircle2 className="h-4 w-4" />Setujui</Button>
                  <Button size="sm" variant="destructive" className="flex-1" onClick={() => { setRejectId(d.id); setNote(""); }} disabled={busy}><XCircle className="h-4 w-4" />Tolak</Button>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
        {data.deposits.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground">Tidak ada deposit {TABS.find(t => t.v === tab)?.label.toLowerCase()}.</div>}
      </div>

      {/* Proof viewer */}
      <Modal open={proof != null} onClose={() => setProof(null)} title="Bukti Pembayaran">
        {proof != null && (
          <div className="flex flex-col gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/deposits/${proof}/proof`} alt="Bukti pembayaran" className="w-full rounded-lg border" />
            <a href={`/api/deposits/${proof}/proof`} target="_blank" rel="noreferrer">
              <Button variant="outline" className="w-full"><ExternalLink className="h-4 w-4" />Buka di tab baru</Button>
            </a>
          </div>
        )}
      </Modal>

      {/* Reject dialog */}
      <Modal open={rejectId != null} onClose={() => setRejectId(null)} title="Tolak Deposit">
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
        title="Setujui Deposit"
        variant="success"
        confirmLabel="Ya, Setujui"
        description="Setujui deposit ini? Saldo user akan langsung bertambah dan mereka akan diberi tahu lewat bot."
      />
    </div>
  );
}
