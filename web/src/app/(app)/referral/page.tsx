"use client";
import { useEffect, useState } from "react";
import { Gift, Info, Users, CheckCircle2, Clock, Wallet, ImageIcon, Trophy } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Badge, Switch } from "@/components/ui/controls";

const rupiah = (n: number) => "Rp" + Number(n || 0).toLocaleString("id-ID");

export default function ReferralPage() {
  const [enabled, setEnabled] = useState(true);
  const [rewardType, setRewardType] = useState<"balance" | "quota">("balance");
  const [rewardAmount, setRewardAmount] = useState(5000);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [list, setList] = useState<any[]>([]);

  const loadSettings = () =>
    api("/api/referral/settings").then((s) => {
      setEnabled(s.enabled); setRewardType(s.reward_type); setRewardAmount(s.reward_amount);
    }).catch(() => {});
  const loadStats = () => api("/api/referral/stats").then(setStats).catch(() => {});
  const loadList = () => api("/api/referral/list").then((d) => setList(d.referrals || [])).catch(() => {});

  useEffect(() => { loadSettings(); loadStats(); loadList(); }, []);

  async function save() {
    if (rewardAmount < 0) { toast.error("Nominal bonus tidak valid"); return; }
    setLoading(true);
    try {
      await api("/api/referral/settings", {
        method: "POST",
        body: JSON.stringify({ enabled, reward_type: rewardType, reward_amount: Number(rewardAmount) }),
      });
      toast.success("Pengaturan referral disimpan");
    } catch { toast.error("Gagal menyimpan"); }
    finally { setLoading(false); }
  }

  const nameOf = (username?: string, firstName?: string, id?: number) =>
    username ? `@${username}` : (firstName || `ID ${id}`);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Referral</h1>
        <p className="text-sm text-muted-foreground">Kelola sistem ajak teman & bonusnya — semua bisa diubah tanpa sentuh kode</p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold">{stats.total}</div><div className="text-xs text-muted-foreground mt-1">Total Referral</div></CardContent></Card>
          <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-emerald-500">{stats.rewarded}</div><div className="text-xs text-muted-foreground mt-1">Sudah Dapat Bonus</div></CardContent></Card>
          <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-amber-500">{stats.pending}</div><div className="text-xs text-muted-foreground mt-1">Menunggu Join Channel</div></CardContent></Card>
          <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-primary">{rupiah(stats.balance_paid)}</div><div className="text-xs text-muted-foreground mt-1">Total Saldo Terbagi</div></CardContent></Card>
        </div>
      )}

      <Card>
        <CardHeader><CardTitle><Gift className="h-4 w-4" />Pengaturan Bonus Referral</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="text-sm font-semibold">Aktifkan Sistem Referral</div>
              <div className="text-xs text-muted-foreground">Jika nonaktif, link referral baru tidak akan dicatat lagi</div>
            </div>
            <Switch checked={enabled} onChange={setEnabled} />
          </div>

          <div className="border-t pt-4">
            <label className="mb-2 block text-sm font-medium">Jenis Bonus untuk Pengundang (Referrer)</label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                onClick={() => setRewardType("balance")}
                className={`flex flex-1 items-center gap-2 rounded-md border px-3 py-2.5 text-sm font-medium transition-colors ${rewardType === "balance" ? "border-primary bg-primary/10 text-primary" : "hover:bg-accent"}`}
              >
                <Wallet className="h-4 w-4" />Tambah Saldo
              </button>
              <button
                onClick={() => setRewardType("quota")}
                className={`flex flex-1 items-center gap-2 rounded-md border px-3 py-2.5 text-sm font-medium transition-colors ${rewardType === "quota" ? "border-primary bg-primary/10 text-primary" : "hover:bg-accent"}`}
              >
                <ImageIcon className="h-4 w-4" />Tambah Kuota Gambar
              </button>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium">
              {rewardType === "balance" ? "Nominal Saldo per Referral Berhasil" : "Jumlah Kuota Gambar per Referral Berhasil"}
            </label>
            <Input
              type="number" min={0} value={rewardAmount}
              onChange={(e) => setRewardAmount(Number(e.target.value))}
              placeholder={rewardType === "balance" ? "mis. 5000" : "mis. 5"}
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              {rewardType === "balance"
                ? `Setiap referral berhasil (teman join channel), pengundang dapat ${rupiah(rewardAmount)} saldo otomatis.`
                : `Setiap referral berhasil (teman join channel), pengundang dapat ${rewardAmount} kuota gambar tambahan (di luar limit harian).`}
            </p>
          </div>
        </CardContent>
      </Card>

      <Button onClick={save} disabled={loading}>{loading ? "Menyimpan..." : "Simpan Pengaturan"}</Button>

      {stats?.top_referrers?.length > 0 && (
        <Card>
          <CardHeader><CardTitle><Trophy className="h-4 w-4" />Top Pengundang</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-0 px-0 pt-0">
            {stats.top_referrers.map((r: any, i: number) => (
              <div key={r.referrer_id} className="flex items-center gap-3 border-b px-5 py-3 last:border-0">
                <Badge variant="muted" className="shrink-0">#{i + 1}</Badge>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{nameOf(r.referrer_username, r.referrer_first_name, r.referrer_id)}</div>
                  <div className="text-xs text-muted-foreground">ID {r.referrer_id}</div>
                </div>
                <div className="text-right text-sm">
                  <div className="font-semibold text-emerald-500">{r.rewarded} berhasil</div>
                  <div className="text-xs text-muted-foreground">{r.total} total diundang</div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle><Users className="h-4 w-4" />Riwayat Referral</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-0 px-0 pt-0">
          {list.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">Belum ada referral</div>}
          {list.map((r) => (
            <div key={r.id} className="flex items-start gap-3 border-b px-5 py-3 last:border-0">
              {r.status === "rewarded"
                ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                : <Clock className="h-4 w-4 shrink-0 text-amber-500 mt-0.5" />}
              <div className="min-w-0 flex-1">
                <div className="text-sm">
                  <span className="font-medium">{nameOf(r.referrer_username, r.referrer_first_name, r.referrer_id)}</span>
                  <span className="text-muted-foreground"> mengundang </span>
                  <span className="font-medium">{nameOf(r.referred_username, r.referred_first_name, r.referred_id)}</span>
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {new Date(r.created_at).toLocaleString("id-ID")}
                  {r.status === "rewarded" && (
                    <> · Bonus: {r.reward_type === "balance" ? rupiah(r.reward_amount) : `${r.reward_amount} kuota`}</>
                  )}
                </div>
              </div>
              <Badge variant={r.status === "rewarded" ? "success" : "muted"}>
                {r.status === "rewarded" ? "berhasil" : "menunggu join"}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Info className="h-4 w-4" />Cara Kerja</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm text-muted-foreground">
          <p>• Setiap user punya link referral unik (menu <b className="text-foreground">Ajak Teman</b> di bot), format <code>https://t.me/nama_bot?start=ref_ID</code>.</p>
          <p>• Bonus ke pengundang dicairkan otomatis <b className="text-foreground">begitu teman yang diundang join channel wajib</b> untuk pertama kali (bukan langsung saat /start, guna mencegah abuse akun palsu).</p>
          <p>• Jenis bonus bisa diatur di sini: <b className="text-foreground">saldo</b> (masuk ke saldo akun, bisa dipakai beli premium) atau <b className="text-foreground">kuota gambar</b> (kuota tambahan di luar limit harian, otomatis kepakai duluan setelah limit harian habis).</p>
          <p>• Perubahan pengaturan di sini hanya berlaku untuk referral BARU — referral yang sudah tercatat sebelumnya tetap pakai jenis/nominal bonus lama (snapshot saat itu).</p>
        </CardContent>
      </Card>
    </div>
  );
}
