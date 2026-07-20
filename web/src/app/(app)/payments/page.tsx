"use client";
import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Landmark, Smartphone, QrCode, CreditCard, Hash, User, Info, ImageIcon } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Badge, Switch } from "@/components/ui/controls";
import { CustomSelect, Modal, Field } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";

const empty = { id: 0, type: "bank", name: "", account_name: "", account_number: "", instructions: "", qr_image: "", is_active: true, sort_order: 0 };

export default function MethodsPage() {
  const { t, lang } = useLang();
  const TYPES = [
    { v: "bank", label: t("payments.type.bank"), icon: Landmark },
    { v: "ewallet", label: t("payments.type.ewallet"), icon: Smartphone },
    { v: "qris", label: t("payments.type.qris"), icon: QrCode },
    { v: "other", label: t("payments.type.other"), icon: CreditCard },
  ];
  const [methods, setMethods] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>(empty);
  const [saving, setSaving] = useState(false);
  const [delTarget, setDelTarget] = useState<any>(null);

  const load = () => api("/api/methods").then((d) => setMethods(d.methods)).catch(() => {});
  useEffect(() => { load(); }, []);

  function openNew() { setForm(empty); setOpen(true); }
  function openEdit(m: any) {
    setForm({ ...m, account_name: m.account_name || "", account_number: m.account_number || "", instructions: m.instructions || "", qr_image: m.qr_image || "" });
    setOpen(true);
  }

  async function save() {
    if (!form.name.trim()) { toast.error(lang === "id" ? "Nama metode wajib diisi" : "Name required"); return; }
    setSaving(true);
    try {
      const body = JSON.stringify(form);
      if (form.id) await api(`/api/methods/${form.id}`, { method: "PUT", body });
      else await api("/api/methods", { method: "POST", body });
      toast.success(form.id ? t("payments.edit") + " OK" : t("payments.add_title") + " OK");
      setOpen(false); load();
    } catch { toast.error(t("settings.failed")); } finally { setSaving(false); }
  }

  async function del() {
    if (!delTarget) return;
    try { await api(`/api/methods/${delTarget.id}`, { method: "DELETE" }); toast.success(t("common.delete") + " OK"); setDelTarget(null); load(); }
    catch { toast.error(t("settings.failed")); }
  }
  const icon = (tp: string) => tp === "bank" ? Landmark : tp === "ewallet" ? Smartphone : tp === "qris" ? QrCode : CreditCard;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("payments.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("payments.sub")}</p>
        </div>
        <Button onClick={openNew}><Plus className="h-4 w-4" />{t("payments.add")}</Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {methods.map((m) => {
          const Ico = icon(m.type);
          return (
            <Card key={m.id}>
              <CardContent className="pt-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <Ico className="h-5 w-5 text-primary" />
                    <span className="text-lg font-bold">{m.name}</span>
                    <Badge variant="muted">{TYPES.find(tt=>tt.v===m.type)?.label || m.type}</Badge>
                  </div>
                  {m.is_active ? <Badge variant="success">active</Badge> : <Badge variant="muted">inactive</Badge>}
                </div>
                <div className="mt-3 flex flex-col gap-1 text-sm text-muted-foreground">
                  {m.account_number && <span className="flex items-center gap-1.5"><Hash className="h-3.5 w-3.5" /> <span className="font-mono text-foreground">{m.account_number}</span></span>}
                  {m.account_name && <span className="flex items-center gap-1.5"><User className="h-3.5 w-3.5" /> {m.account_name}</span>}
                  {m.instructions && <span className="flex items-center gap-1.5 text-xs"><Info className="h-3 w-3" /> {m.instructions}</span>}
                  {m.qr_image && <span className="flex items-center gap-1.5 text-xs"><ImageIcon className="h-3 w-3" /> {t("payments.qr_saved")}</span>}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button size="sm" variant="outline" className="flex-1" onClick={() => openEdit(m)}><Pencil className="h-4 w-4" />{t("common.edit")}</Button>
                  <Button size="sm" variant="destructive" onClick={() => setDelTarget(m)}><Trash2 className="h-4 w-4" /></Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
        {methods.length === 0 && <div className="col-span-full py-10 text-center text-sm text-muted-foreground">{t("payments.empty")}</div>}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={form.id ? t("payments.edit") : t("payments.add_title")}>
        <Field label={t("payments.type")}>
          <CustomSelect value={form.type} onChange={(v) => setForm({ ...form, type: v })} options={TYPES.map(tt=>({value:tt.v,label:tt.label}))} />
        </Field>
        <Field label={t("payments.name")}><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={t("payments.name_ph")} /></Field>
        <Field label={t("payments.number")}><Input value={form.account_number} onChange={(e) => setForm({ ...form, account_number: e.target.value })} placeholder="1234567890" /></Field>
        <Field label={t("payments.holder")}><Input value={form.account_name} onChange={(e) => setForm({ ...form, account_name: e.target.value })} placeholder={t("payments.holder_ph")} /></Field>
        <Field label={t("payments.instructions")}><Textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} placeholder={t("payments.instructions_ph")} /></Field>
        {form.type === "qris" && <Field label={t("payments.qr")}><Input value={form.qr_image} onChange={(e) => setForm({ ...form, qr_image: e.target.value })} placeholder="file_id" /></Field>}
        <div className="mb-4 flex items-center justify-between">
          <span className="text-sm font-medium">{t("payments.active")}</span>
          <Switch checked={form.is_active} onChange={(v) => setForm({ ...form, is_active: v })} />
        </div>
        <Button className="w-full" onClick={save} disabled={saving}>{saving ? t("payments.saving") : t("payments.save")}</Button>
      </Modal>

      <ConfirmDialog open={delTarget != null} onClose={() => setDelTarget(null)} onConfirm={del} variant="destructive"
        title={t("payments.delete_title")} confirmLabel={t("common.yes_delete")} description={<>{t("payments.delete_desc", { name: delTarget?.name || "" })}</>} />
    </div>
  );
}
