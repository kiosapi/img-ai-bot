"use client";
import { useEffect, useState } from "react";
import { Wallet, Info, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Switch, Badge } from "@/components/ui/controls";

const rupiah = (n: number) => "Rp" + Number(n || 0).toLocaleString("id-ID");

export default function BalanceSettingsPage() {
  const [enabled, setEnabled] = useState(true);
  const [minAmount, setMinAmount] = useState(10000);
  const [maxAmount, setMaxAmount] = useState(5000000);
  const [quick, setQuick] = useState<number[]>([10000, 25000, 50000, 100000, 250000]);
  const [newQuick, setNewQuick] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api("/api/balance/settings").then((s) => {
      setEnabled(s.enabled); setMinAmount(s.min_amount); setMaxAmount(s.max_amount); setQuick(s.quick_amounts || []);
    }).catch(() => {});
  }, []);

  function addQuick() {
    const v = Number(newQuick.replace(/\D/g, ""));
    if (!v || v <= 0) { toast.error("Nominal tidak valid"); return; }
    if (quick.includes(v)) { toast.error("Nominal sudah ada"); return; }
    setQuick([...quick, v].sort((a, b) => a - b));
    setNewQuick("");
  }

  function removeQuick(v: number) {
    setQuick(quick.filter((x) => x !== v));
  }

  async function save() {
    if (minAmount < 0 || maxAmount < minAmount) { toast.error("Rentang nominal tidak valid"); return; }
    setLoading(true);
    try {
      await api("/api/balance/settings", {
        method: "POST",
        body: JSON.stringify({ enabled, min_amount: Number(minAmount), max_amount: Number(maxAmount), quick_amounts: quick }),
      });
      toast.success("Pengaturan saldo disimpan");
    } catch { toast.error("Gagal menyimpan"); }
    finally { setLoading(false); }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Pengaturan Saldo</h1>
        <p className="text-sm text-muted-foreground">Kelola fitur deposit & top up saldo — semua bisa diubah di sini tanpa perlu ubah kode</p>
      </div>

      <Card>
        <CardHeader><CardTitle><Wallet className="h-4 w-4" />Fitur Saldo</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="text-sm font-semibold">Aktifkan Top Up Saldo</div>
              <div className="text-xs text-muted-foreground">Jika nonaktif, tombol top up di bot disembunyikan/nonaktif</div>
            </div>
            <Switch checked={enabled} onChange={setEnabled} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2 border-t pt-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium">Nominal Minimum</label>
              <Input type="number" min={0} value={minAmount} onChange={(e) => setMinAmount(Number(e.target.value))} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">Nominal Maksimum</label>
              <Input type="number" min={0} value={maxAmount} onChange={(e) => setMaxAmount(Number(e.target.value))} />
            </div>
          </div>

          <div className="border-t pt-4">
            <label className="mb-2 block text-sm font-medium">Pilihan Nominal Cepat (quick amount) di bot</label>
            <div className="mb-3 flex flex-wrap gap-2">
              {quick.map((v) => (
                <Badge key={v} variant="default" className="gap-1.5 py-1 pl-3 pr-1.5 text-sm">
                  {rupiah(v)}
                  <button onClick={() => removeQuick(v)} className="rounded-full p-0.5 hover:bg-primary/20"><X className="h-3.5 w-3.5" /></button>
                </Badge>
              ))}
              {quick.length === 0 && <span className="text-sm text-muted-foreground">Belum ada nominal cepat.</span>}
            </div>
            <div className="flex gap-2">
              <Input placeholder="mis. 50000" value={newQuick} onChange={(e) => setNewQuick(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addQuick()} />
              <Button variant="outline" onClick={addQuick}><Plus className="h-4 w-4" />Tambah</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Button onClick={save} disabled={loading}>{loading ? "Menyimpan..." : "Simpan Pengaturan"}</Button>

      <Card>
        <CardHeader><CardTitle><Info className="h-4 w-4" />Cara Kerja</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm text-muted-foreground">
          <p>• User top up saldo lewat bot: pilih nominal (quick amount atau custom) → pilih metode pembayaran → upload bukti transfer.</p>
          <p>• Admin verifikasi bukti di menu <b className="text-foreground">Deposit</b>, saldo user bertambah otomatis setelah disetujui.</p>
          <p>• Saldo dipakai user untuk beli paket Premium secara instan (potong saldo otomatis, tanpa perlu upload bukti lagi).</p>
          <p>• Metode pembayaran yang dipakai sama dengan metode di menu <b className="text-foreground">Pembayaran</b>.</p>
        </CardContent>
      </Card>
    </div>
  );
}
