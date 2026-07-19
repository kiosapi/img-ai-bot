"use client";
import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Landmark, Smartphone, QrCode, CreditCard } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Badge, Switch } from "@/components/ui/controls";
import { Modal, Field, Select } from "@/components/ui/modal";

const empty = { id: 0, type: "bank", name: "", account_name: "", account_number: "", instructions: "", qr_image: "", is_active: true, sort_order: 0 };
const TYPES = [
  { v: "bank", label: "🏦 Bank Transfer" },
  { v: "ewallet", label: "📱 E-Wallet" },
  { v: "qris", label: "🔳 QRIS" },
  { v: "other", label: "💳 Lainnya" },
];
const icon = (t: string) => t === "bank" ? Landmark : t === "ewallet" ? Smartphone : t === "qris" ? QrCode : CreditCard;

export default function MethodsPage() {
  const [methods, setMethods] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>(empty);
  const [saving, setSaving] = useState(false);

  const load = () => api("/api/methods").then((d) => setMethods(d.methods)).catch(() => {});
  useEffect(() => { load(); }, []);

  function openNew() { setForm(empty); setOpen(true); }
  function openEdit(m: any) {
    setForm({ ...m, account_name: m.account_name || "", account_number: m.account_number || "", instructions: m.instructions || "", qr_image: m.qr_image || "" });
    setOpen(true);
  }

  async function save() {
    if (!form.name.trim()) { toast.error("Nama metode wajib diisi"); return; }
    setSaving(true);
    try {
      const body = JSON.stringify(form);
      if (form.id) await api(`/api/methods/${form.id}`, { method: "PUT", body });
      else await api("/api/methods", { method: "POST", body });
      toast.success(form.id ? "Metode diperbarui" : "Metode ditambahkan");
      setOpen(false); load();
    } catch { toast.error("Gagal menyimpan"); } finally { setSaving(false); }
  }

  async function del(m: any) {
    if (!confirm(`Hapus metode "${m.name}"?`)) return;
    try { await api(`/api/methods/${m.id}`, { method: "DELETE" }); toast.success("Metode dihapus"); load(); }
    catch { toast.error("Gagal menghapus"); }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Metode Pembayaran</h1>
          <p className="text-sm text-muted-foreground">Kelola rekening & channel pembayaran</p>
        </div>
        <Button onClick={openNew}><Plus className="h-4 w-4" />Tambah</Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {methods.map((m) => {
          const Icon = icon(m.type);
          return (
            <Card key={m.id}>
              <CardContent className="pt-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-primary" />
                    <span className="text-lg font-bold">{m.name}</span>
                    <Badge variant="muted">{m.type}</Badge>
                  </div>
                  {m.is_active ? <Badge variant="success">aktif</Badge> : <Badge variant="muted">nonaktif</Badge>}
                </div>
                <div className="mt-3 flex flex-col gap-1 text-sm text-muted-foreground">
                  {m.account_number && <span>📌 <span className="font-mono text-foreground">{m.account_number}</span></span>}
                  {m.account_name && <span>👤 {m.account_name}</span>}
                  {m.instructions && <span className="text-xs">ℹ️ {m.instructions}</span>}
                  {m.qr_image && <span className="text-xs">🖼️ QR image tersimpan</span>}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button size="sm" variant="outline" className="flex-1" onClick={() => openEdit(m)}><Pencil className="h-4 w-4" />Edit</Button>
                  <Button size="sm" variant="destructive" onClick={() => del(m)}><Trash2 className="h-4 w-4" /></Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
        {methods.length === 0 && <div className="col-span-full py-10 text-center text-sm text-muted-foreground">Belum ada metode. Tekan Tambah.</div>}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={form.id ? "Edit Metode" : "Tambah Metode"}>
        <Field label="Jenis"><Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{TYPES.map((t) => <option key={t.v} value={t.v}>{t.label}</option>)}</Select></Field>
        <Field label="Nama"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="BCA / DANA / QRIS" /></Field>
        <Field label="Nomor / ID (rekening, no HP, dll)"><Input value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} placeholder="1234567890" /></Field>
        <Field label="Atas Nama"><Input value={form.account_name} onChange={(e) => setForm({ ...form, account_name: e.target.value })} placeholder="Nama pemilik" /></Field>
        <Field label="Instruksi Tambahan (opsional)"><Textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} placeholder="Catatan buat user" /></Field>
        {form.type === "qris" && <Field label="QR Image file_id (opsional, dari Telegram)"><Input value={form.qr_image} onChange={(e) => setForm({ ...form, qr_image: e.target.value })} placeholder="file_id foto QRIS" /></Field>}
        <div className="mb-4 flex items-center justify-between">
          <span className="text-sm font-medium">Status Aktif</span>
          <Switch checked={form.is_active} onChange={(v) => setForm({ ...form, is_active: v })} />
        </div>
        <Button className="w-full" onClick={save} disabled={saving}>{saving ? "Menyimpan..." : "Simpan"}</Button>
      </Modal>
    </div>
  );
}
