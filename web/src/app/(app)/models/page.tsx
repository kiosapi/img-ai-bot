"use client";
import { useEffect, useState } from "react";
import { Bot, Key, RefreshCw, Power, Star, Trash2, Save, Plus, Eye, EyeOff, Check, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Switch } from "@/components/ui/controls";
import { CustomSelect } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";

type Provider = { id: string; name: string; base_url: string; is_active: boolean; has_api_key: boolean; api_key_masked: string; base_url_setting: string; };
type Model = { id: string; external_id: string; provider_id: string; display_name: string; description: string; is_active: boolean; is_default: boolean; sort_order: number; provider_name: string; provider_active: boolean; };

export default function ModelsPage() {
  const { t, lang } = useLang();
  const PROVIDER_OPTIONS = [
    { value: "rightcodes", label: "Right Codes" },
    { value: "cubence", label: "Cubence" },
    { value: "apikeyfun", label: "ApiKey Fun" },
    { value: "unity2", label: "Unity2" },
  ];

  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [apikeys, setApikeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [newModel, setNewModel] = useState({ id: "", provider_id: "unity2", display_name: "", description: "", is_active: true });
  const [editingKeys, setEditingKeys] = useState<Record<string, { key: string; base: string }>>({
    cubence: { key: "", base: "" }, rightcodes: { key: "", base: "" }, apikeyfun: { key: "", base: "" }, unity2: { key: "", base: "" },
  });
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function loadAll() {
    setLoading(true);
    try {
      const [prov, mods, keys] = await Promise.all([api("/api/providers"), api("/api/models"), api("/api/apikeys")]);
      setProviders(prov); setModels(mods); setApikeys(keys);
      const ek: any = {};
      for (const k of keys) ek[k.provider_id] = { key: "", base: k.base_url || "" };
      setEditingKeys((prev) => {
        const merged: any = { ...prev };
        for (const pid of Object.keys(ek)) merged[pid] = { key: "", base: prev[pid]?.base || ek[pid]?.base || "" };
        if (!merged.cubence) merged.cubence = { key: "", base: "" };
        if (!merged.rightcodes) merged.rightcodes = { key: "", base: "" };
        if (!merged.apikeyfun) merged.apikeyfun = { key: "", base: "" };
        if (!merged.unity2) merged.unity2 = { key: "", base: "" };
        return merged;
      });
    } catch { toast.error(lang==="id"?"Gagal memuat data":"Failed to load"); } finally { setLoading(false); }
  }
  useEffect(() => { loadAll(); }, []);

  async function saveApiKey(pid: string) {
    const draft = editingKeys[pid]; if (!draft) return;
    if (!draft.key && !draft.base) { toast.error(lang==="id"?"Isi API key atau Base URL":"Fill API key or Base URL"); return; }
    try {
      await api("/api/apikeys", { method: "POST", body: JSON.stringify({ provider_id: pid, api_key: draft.key || "***", base_url: draft.base || undefined }) });
      toast.success(`API key ${pid} ${lang==="id"?"disimpan":"saved"}`);
      setEditingKeys((prev) => ({ ...prev, [pid]: { key: "", base: prev[pid]?.base || "" } }));
      loadAll();
    } catch (e: any) { toast.error(e.message || "Gagal"); }
  }
  async function toggleProvider(pid: string) {
    try { await api(`/api/providers/${pid}/toggle`, { method: "POST" }); toast.success(`Provider ${pid} toggled`); loadAll(); } catch { toast.error("Gagal"); }
  }
  async function syncModels(pid: string) {
    try { toast.info(`Sync ${pid}...`); const res = await api(`/api/providers/${pid}/sync-models`, { method: "POST" }); toast.success(`Synced ${res.synced} models`); loadAll(); } catch (e: any) { toast.error(e.message || "Gagal"); }
  }
  async function toggleModel(mid: string) { try { await api(`/api/models/${encodeURIComponent(mid)}/toggle`, { method: "POST" }); loadAll(); } catch { toast.error("Gagal"); } }
  async function setDefault(mid: string) { try { await api(`/api/models/${encodeURIComponent(mid)}/default`, { method: "POST" }); toast.success(t("models.default_set")); loadAll(); } catch { toast.error("Gagal"); } }
  async function confirmDeleteModel() {
    if (!deleteTarget) return; setDeleting(true);
    try { await api(`/api/models/${encodeURIComponent(deleteTarget)}`, { method: "DELETE" }); toast.success(lang==="id"?"Model dihapus":"Model deleted"); setDeleteTarget(null); loadAll(); } catch { toast.error("Gagal"); } finally { setDeleting(false); }
  }
  async function createModel() {
    if (!newModel.id || !newModel.display_name) { toast.error(lang==="id"?"ID dan nama wajib":"ID and display name required"); return; }
    try {
      await api("/api/models", { method: "POST", body: JSON.stringify({ id: newModel.id, provider_id: newModel.provider_id, display_name: newModel.display_name, description: newModel.description, is_active: newModel.is_active, is_default: false, sort_order: 0 }) });
      toast.success(lang==="id"?"Model dibuat":"Model created"); setNewModel({ id: "", provider_id: "unity2", display_name: "", description: "", is_active: true }); loadAll();
    } catch (e: any) { toast.error(e.message || "Gagal"); }
  }

  if (loading) return <div className="p-4 md:p-6">{t("models.loading")}</div>;

  return (
    <div className="flex flex-col gap-4 md:gap-6 p-1">
      <div className="space-y-1">
        <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2"><Bot className="h-5 w-5 md:h-6 md:w-6 shrink-0" /> {t("models.title")}</h1>
        <p className="text-xs md:text-sm text-muted-foreground">{t("models.sub")}</p>
      </div>

      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><Key className="h-4 w-4" /> {t("models.api_keys")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3 md:gap-4">
          {apikeys.map((k) => (
            <div key={k.provider_id} className="rounded-lg border p-3 md:p-4 flex flex-col gap-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold uppercase text-sm flex items-center gap-2">{k.provider_id}
                    {k.has_key ? <span className="inline-flex items-center gap-1 text-[11px] font-normal text-emerald-600"><Check className="h-3 w-3" /> key set</span> : <span className="inline-flex items-center gap-1 text-[11px] font-normal text-red-500"><X className="h-3 w-3" /> {lang==="id"?"belum di-set":"not set"}</span>}
                  </div>
                  <div className="text-xs text-muted-foreground break-all">Key {k.masked || (lang==="id"?"belum di-set":"not set")} | Len {k.api_key_length} | Base {k.base_url || "-"}</div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" variant="outline" onClick={() => syncModels(k.provider_id)}><RefreshCw className="h-4 w-4 mr-1" /> {t("models.sync")}</Button>
                  <Button size="sm" variant="outline" onClick={() => toggleProvider(k.provider_id)}><Power className="h-4 w-4 mr-1" /> {t("models.toggle")}</Button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs font-medium">{t("models.new_key")}</label>
                  <div className="relative">
                    <Input type={showKey[k.provider_id] ? "text" : "password"} placeholder={k.has_key ? (lang==="id"?"Kosongkan jika tidak ubah":"Leave empty to keep") : "sk-..."} value={editingKeys[k.provider_id]?.key || ""} onChange={(e) => setEditingKeys((p) => ({ ...p, [k.provider_id]: { ...(p[k.provider_id] || { key: "", base: "" }), key: e.target.value } }))} />
                    <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground" onClick={() => setShowKey((s) => ({ ...s, [k.provider_id]: !s[k.provider_id] }))}>{showKey[k.provider_id] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium">{t("models.base_url")}</label>
                  <Input placeholder={k.provider_id === "rightcodes" ? "https://www.right.codes/draw" : k.provider_id === "apikeyfun" ? "https://api.apikey.fun/v1" : k.provider_id === "unity2" ? "https://api.unity2.ai/v1" : "https://api-dmit.cubence.com"} value={editingKeys[k.provider_id]?.base ?? ""} onChange={(e) => setEditingKeys((p) => ({ ...p, [k.provider_id]: { ...(p[k.provider_id] || { key: "", base: "" }), base: e.target.value } }))} />
                </div>
              </div>
              <Button size="sm" onClick={() => saveApiKey(k.provider_id)} className="w-full sm:w-fit"><Save className="h-4 w-4 mr-1" /> {t("models.save_key")}</Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><Bot className="h-4 w-4" /> {t("models.providers")}</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {providers.map((p) => (
            <div key={p.id} className="flex items-center justify-between border rounded-lg p-3">
              <div className="min-w-0">
                <div className="font-medium text-sm truncate">{p.id} <span className={`ml-2 text-[11px] px-1.5 py-0.5 rounded ${p.is_active ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30" : "bg-red-100 text-red-700 dark:bg-red-900/30"}`}>{p.is_active ? "active" : "inactive"}</span></div>
                <div className="text-xs text-muted-foreground truncate">{p.base_url}</div>
                <div className="text-[11px] text-muted-foreground">key {p.api_key_masked || "-"}</div>
              </div>
              <Switch checked={p.is_active} onChange={() => toggleProvider(p.id)} />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><Plus className="h-4 w-4" /> {t("models.add_manual")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Input placeholder={t("models.model_id_ph")} value={newModel.id} onChange={(e) => setNewModel((p) => ({ ...p, id: e.target.value }))} />
            <Input placeholder={t("models.display_name_ph")} value={newModel.display_name} onChange={(e) => setNewModel((p) => ({ ...p, display_name: e.target.value }))} />
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">{t("models.provider")}</label>
              <CustomSelect value={newModel.provider_id} onChange={(v) => setNewModel((p) => ({ ...p, provider_id: v }))} options={PROVIDER_OPTIONS} />
            </div>
            <Input placeholder={t("models.desc_ph")} value={newModel.description} onChange={(e) => setNewModel((p) => ({ ...p, description: e.target.value }))} />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs">{t("models.active")}</span><Switch checked={newModel.is_active} onChange={(v: boolean) => setNewModel((p) => ({ ...p, is_active: v }))} />
            <Button size="sm" onClick={createModel}><Plus className="h-4 w-4 mr-1" /> {t("models.create")}</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-base">{t("models.list")} ({models.length})</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 max-h-[800px] overflow-auto">
          {models.map((m) => (
            <div key={m.id} className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 border rounded-lg p-3">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate flex items-center gap-1.5">
                  <span className="truncate">{m.display_name}</span>
                  {m.is_default && <span className="inline-flex items-center text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded dark:bg-amber-900/30 shrink-0"><Star className="h-3 w-3 mr-0.5" /> default</span>}
                  <span className={`inline-flex text-[10px] px-1.5 py-0.5 rounded shrink-0 ${m.is_active ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800"}`}>{m.is_active ? "active" : "inactive"}</span>
                </div>
                <div className="text-xs font-mono truncate text-muted-foreground">id {m.id} | ext {m.external_id || m.id.split(":").slice(1).join(":") || m.id} | provider {m.provider_id} {m.provider_active ? "" : "(provider off)"}</div>
                <div className="text-[11px] text-muted-foreground truncate">{m.description || "-"}</div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-auto">
                <Button size="sm" variant="outline" onClick={() => setDefault(m.id)} title="Set default"><Star className="h-4 w-4" /></Button>
                <Switch checked={m.is_active} onChange={() => toggleModel(m.id)} />
                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(m.id)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            </div>
          ))}
          {models.length === 0 && <div className="text-sm text-muted-foreground py-4 text-center">{t("models.no_models")}</div>}
        </CardContent>
      </Card>

      <ConfirmDialog open={deleteTarget !== null} onClose={() => setDeleteTarget(null)} onConfirm={confirmDeleteModel} loading={deleting}
        title={t("models.delete_title")} variant="destructive" confirmLabel={t("models.delete_yes")}
        description={<>{t("models.delete_desc", { id: deleteTarget || "" })}</>} />
    </div>
  );
}
