"use client";
import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Crown, BarChart3, Hourglass, StickyNote, Infinity as InfinityIcon } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Badge, Switch } from "@/components/ui/controls";
import { Modal, Field } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";

const empty = { id: 0, name: "", daily_limit: 100, price: 0, duration_days: 30, description: "", is_active: true, sort_order: 0 };

export default function PlansPage() {
  const { t, lang } = useLang();
  const [plans, setPlans] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>(empty);
  const [saving, setSaving] = useState(false);
  const [delTarget, setDelTarget] = useState<any>(null);

  const load = () => api("/api/plans").then((d) => setPlans(d.plans)).catch(() => {});
  useEffect(() => { load(); }, []);
  function openNew() { setForm(empty); setOpen(true); }
  function openEdit(p: any) { setForm({ ...p, description: p.description || "" }); setOpen(true); }
  async function save() {
    if (!form.name.trim()) { toast.error(lang === "id" ? "Nama paket wajib" : "Plan name required"); return; }
    setSaving(true);
    try {
      const body = JSON.stringify(form);
      if (form.id) await api(`/api/plans/${form.id}`, { method: "PUT", body });
      else await api("/api/plans", { method: "POST", body });
      toast.success(form.id ? t("plans.edit") + " OK" : t("plans.add_title") + " OK");
      setOpen(false); load();
    } catch { toast.error("Gagal"); } finally { setSaving(false); }
  }
  async function del() {
    if (!delTarget) return;
    try { await api(`/api/plans/${delTarget.id}`, { method: "DELETE" }); toast.success(t("plans.delete_title") + " OK"); setDelTarget(null); load(); }
    catch { toast.error("Gagal"); }
  }
  const rupiah = (n: number) => "Rp" + n.toLocaleString("id-ID");
  return (
    <div className="flex flex-col gap-5 w-full min-w-0 max-w-full">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("plans.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("plans.sub")}</p>
        </div>
        <Button onClick={openNew}><Plus className="h-4 w-4" />{t("plans.add")}</Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {plans.map((p) => (
          <Card key={p.id}>
            <CardContent className="pt-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2"><Crown className="h-5 w-5 text-amber-500" /><span className="text-lg font-bold">{p.name}</span></div>
                {p.is_active ? <Badge variant="success">active</Badge> : <Badge variant="muted">inactive</Badge>}
              </div>
              <div className="mt-3 text-2xl font-extrabold">{rupiah(p.price)}</div>
              <div className="mt-2 flex flex-col gap-1 text-sm text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  {p.daily_limit === 0 ? <InfinityIcon className="h-3.5 w-3.5" /> : <BarChart3 className="h-3.5 w-3.5" />}
                  {p.daily_limit === 0 ? t("plans.unlimited") : t("plans.quota_label", { v: `${p.daily_limit}${t("plans.per_day")}` })}
                </span>
                <span className="flex items-center gap-1.5"><Hourglass className="h-3.5 w-3.5" /> {t("plans.active_days", { n: p.duration_days })}</span>
                {p.description && <span className="flex items-center gap-1.5 text-xs"><StickyNote className="h-3 w-3" /> {p.description}</span>}
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="outline" className="flex-1" onClick={() => openEdit(p)}><Pencil className="h-4 w-4" />{t("common.edit")}</Button>
                <Button size="sm" variant="destructive" onClick={() => setDelTarget(p)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {plans.length === 0 && <div className="col-span-full py-10 text-center text-sm text-muted-foreground">{t("plans.empty")}</div>}
      </div>

      <Modal open={open} onClose={() => setOpen(false)} title={form.id ? t("plans.edit") : t("plans.add_title")}>
        <Field label={t("plans.name")}><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={t("plans.name_ph")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("plans.price")}><Input type="number" value={form.price} onChange={(e) => setForm({ ...form, price: +e.target.value })} /></Field>
          <Field label={t("plans.duration")}><Input type="number" value={form.duration_days} onChange={(e) => setForm({ ...form, duration_days: +e.target.value })} /></Field>
        </div>
        <Field label={t("plans.quota")}><Input type="number" value={form.daily_limit} onChange={(e) => setForm({ ...form, daily_limit: +e.target.value })} /></Field>
        <Field label={t("plans.desc")}><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder={t("plans.desc_ph")} /></Field>
        <div className="mb-4 flex items-center justify-between">
          <span className="text-sm font-medium">{t("plans.active")}</span>
          <Switch checked={form.is_active} onChange={(v) => setForm({ ...form, is_active: v })} />
        </div>
        <Button className="w-full" onClick={save} disabled={saving}>{saving ? t("plans.saving") : t("plans.save")}</Button>
      </Modal>

      <ConfirmDialog open={delTarget != null} onClose={() => setDelTarget(null)} onConfirm={del} variant="destructive"
        title={t("plans.delete_title")} confirmLabel={t("common.yes_delete")} description={<>{t("plans.delete_desc", { name: delTarget?.name || "" })}</>} />
    </div>
  );
}
