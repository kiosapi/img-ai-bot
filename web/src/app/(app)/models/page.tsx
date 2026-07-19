"use client";
import { useEffect, useState } from "react";
import { Bot, Key, RefreshCw, Power, Star, Trash2, Save, Plus, Eye, EyeOff, Check, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Switch } from "@/components/ui/controls";

type Provider = {
  id: string;
  name: string;
  base_url: string;
  is_active: boolean;
  has_api_key: boolean;
  api_key_masked: string;
  base_url_setting: string;
};
type Model = {
  id: string;
  external_id: string;
  provider_id: string;
  display_name: string;
  description: string;
  is_active: boolean;
  is_default: boolean;
  sort_order: number;
  provider_name: string;
  provider_active: boolean;
};

export default function ModelsPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [apikeys, setApikeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});

  const [newModel, setNewModel] = useState({ id: "", provider_id: "rightcodes", display_name: "", description: "", is_active: true });
  const [editingKeys, setEditingKeys] = useState<Record<string, { key: string; base: string }>>({
    cubence: { key: "", base: "" },
    rightcodes: { key: "", base: "" },
  });

  async function loadAll() {
    setLoading(true);
    try {
      const [prov, mods, keys] = await Promise.all([
        api("/api/providers"),
        api("/api/models"),
        api("/api/apikeys"),
      ]);
      setProviders(prov);
      setModels(mods);
      setApikeys(keys);
      const ek: any = {};
      for (const k of keys) {
        ek[k.provider_id] = { key: "", base: k.base_url || "" };
      }
      setEditingKeys((prev) => {
        const merged: any = { ...prev };
        for (const pid of Object.keys(ek)) {
          merged[pid] = { key: "", base: prev[pid]?.base || ek[pid]?.base || "" };
        }
        if (!merged.cubence) merged.cubence = { key: "", base: "" };
        if (!merged.rightcodes) merged.rightcodes = { key: "", base: "" };
        return merged;
      });
    } catch (e) {
      toast.error("Gagal memuat data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadAll(); }, []);

  async function saveApiKey(pid: string) {
    const draft = editingKeys[pid];
    if (!draft) return;
    if (!draft.key && !draft.base) {
      toast.error("Isi API key atau Base URL");
      return;
    }
    try {
      await api("/api/apikeys", {
        method: "POST",
        body: JSON.stringify({ provider_id: pid, api_key: draft.key || "***", base_url: draft.base || undefined }),
      });
      toast.success(`API key ${pid} disimpan`);
      setEditingKeys((prev) => ({ ...prev, [pid]: { key: "", base: prev[pid]?.base || "" } }));
      loadAll();
    } catch (e: any) {
      toast.error(e.message || "Gagal simpan");
    }
  }

  async function toggleProvider(pid: string) {
    try {
      await api(`/api/providers/${pid}/toggle`, { method: "POST" });
      toast.success(`Provider ${pid} toggled`);
      loadAll();
    } catch { toast.error("Gagal"); }
  }

  async function syncModels(pid: string) {
    try {
      toast.info(`Sync models ${pid}...`);
      const res = await api(`/api/providers/${pid}/sync-models`, { method: "POST" });
      toast.success(`Synced ${res.synced} models`);
      loadAll();
    } catch (e: any) {
      toast.error(e.message || "Gagal sync, cek API key dulu");
    }
  }

  async function toggleModel(mid: string) {
    try {
      await api(`/api/models/${encodeURIComponent(mid)}/toggle`, { method: "POST" });
      loadAll();
    } catch { toast.error("Gagal toggle model"); }
  }

  async function setDefault(mid: string) {
    try {
      await api(`/api/models/${encodeURIComponent(mid)}/default`, { method: "POST" });
      toast.success("Default diatur");
      loadAll();
    } catch { toast.error("Gagal"); }
  }

  async function deleteModel(mid: string) {
    if (!confirm(`Hapus model ${mid}?`)) return;
    try {
      await api(`/api/models/${encodeURIComponent(mid)}`, { method: "DELETE" });
      toast.success("Model dihapus");
      loadAll();
    } catch { toast.error("Gagal hapus"); }
  }

  async function createModel() {
    if (!newModel.id || !newModel.display_name) {
      toast.error("ID dan display name wajib");
      return;
    }
    try {
      await api("/api/models", {
        method: "POST",
        body: JSON.stringify({
          id: newModel.id,
          provider_id: newModel.provider_id,
          display_name: newModel.display_name,
          description: newModel.description,
          is_active: newModel.is_active,
          is_default: false,
          sort_order: 0,
        }),
      });
      toast.success("Model dibuat");
      setNewModel({ id: "", provider_id: "rightcodes", display_name: "", description: "", is_active: true });
      loadAll();
    } catch (e: any) {
      toast.error(e.message || "Gagal buat model");
    }
  }

  if (loading) return <div className="p-4 md:p-6">Memuat...</div>;

  return (
    <div className="flex flex-col gap-4 md:gap-6 p-1">
      <div className="space-y-1">
        <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2"><Bot className="h-5 w-5 md:h-6 md:w-6 shrink-0" /> Models and Providers</h1>
        <p className="text-xs md:text-sm text-muted-foreground">API key edit via admin tanpa ubah code. Base URL ambil dari settings, bisa diubah per provider. Model ID collision-safe: internal id format provider:external, external = real upstream name. User bot hanya lihat display name, tidak tahu provider.</p>
      </div>

      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><Key className="h-4 w-4" /> API Keys Management</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3 md:gap-4">
          {apikeys.map((k) => (
            <div key={k.provider_id} className="rounded-lg border p-3 md:p-4 flex flex-col gap-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold uppercase text-sm flex items-center gap-2">
                    {k.provider_id}
                    {k.has_key ? <span className="inline-flex items-center gap-1 text-[11px] font-normal text-emerald-600"><Check className="h-3 w-3" /> key set</span> : <span className="inline-flex items-center gap-1 text-[11px] font-normal text-red-500"><X className="h-3 w-3" /> belum di-set</span>}
                  </div>
                  <div className="text-xs text-muted-foreground break-all">Key {k.masked || "belum di-set"} | Len {k.api_key_length} | Base {k.base_url || "-"}</div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" variant="outline" onClick={() => syncModels(k.provider_id)}><RefreshCw className="h-4 w-4 mr-1" /> Sync</Button>
                  <Button size="sm" variant="outline" onClick={() => toggleProvider(k.provider_id)}><Power className="h-4 w-4 mr-1" /> Toggle</Button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs font-medium">API Key baru</label>
                  <div className="relative">
                    <Input type={showKey[k.provider_id] ? "text" : "password"} placeholder={k.has_key ? "Kosongkan jika tidak ubah" : "sk-..."} value={editingKeys[k.provider_id]?.key || ""} onChange={(e) => setEditingKeys((p) => ({ ...p, [k.provider_id]: { ...(p[k.provider_id] || { key: "", base: "" }), key: e.target.value } }))} />
                    <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground" onClick={() => setShowKey((s) => ({ ...s, [k.provider_id]: !s[k.provider_id] }))}>{showKey[k.provider_id] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium">Base URL (editable, bukan hardcoded)</label>
                  <Input placeholder={k.provider_id === "rightcodes" ? "https://www.right.codes/draw" : "https://api-dmit.cubence.com"} value={editingKeys[k.provider_id]?.base ?? ""} onChange={(e) => setEditingKeys((p) => ({ ...p, [k.provider_id]: { ...(p[k.provider_id] || { key: "", base: "" }), base: e.target.value } }))} />
                  <div className="text-[10px] text-muted-foreground">Kosongkan untuk pakai default dari settings. Field ini disimpan ke DB, bukan hardcoded.</div>
                </div>
              </div>
              <Button size="sm" onClick={() => saveApiKey(k.provider_id)} className="w-full sm:w-fit"><Save className="h-4 w-4 mr-1" /> Simpan Key and URL</Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><Bot className="h-4 w-4" /> Providers</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-2">
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
        <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><Plus className="h-4 w-4" /> Tambah Model Manual</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <Input placeholder="model id real, contoh nano-banana-fast" value={newModel.id} onChange={(e) => setNewModel((p) => ({ ...p, id: e.target.value }))} />
            <Input placeholder="Display name user-facing tanpa provider" value={newModel.display_name} onChange={(e) => setNewModel((p) => ({ ...p, display_name: e.target.value }))} />
            <select className="border rounded-md px-3 py-2 text-sm bg-background w-full" value={newModel.provider_id} onChange={(e) => setNewModel((p) => ({ ...p, provider_id: e.target.value }))}>
              <option value="rightcodes">rightcodes</option>
              <option value="cubence">cubence</option>
            </select>
            <Input placeholder="Description optional" value={newModel.description} onChange={(e) => setNewModel((p) => ({ ...p, description: e.target.value }))} />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs">Aktif</span><Switch checked={newModel.is_active} onChange={(v: boolean) => setNewModel((p) => ({ ...p, is_active: v }))} />
            <Button size="sm" onClick={createModel}><Plus className="h-4 w-4 mr-1" /> Buat Model</Button>
          </div>
          <div className="text-xs text-muted-foreground">Sistem collision-safe: jika gpt-image-2 ada di cubence dan rightcodes, internal id jadi cubence:gpt-image-2 dan rightcodes:gpt-image-2, tidak double hilang. external_id yang dikirim ke upstream.</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-base">Models List ({models.length}) - Toggle Active per Model</CardTitle></CardHeader>
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
                <Button size="sm" variant="ghost" onClick={() => deleteModel(m.id)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            </div>
          ))}
          {models.length === 0 && <div className="text-sm text-muted-foreground py-4 text-center">Belum ada model. Isi API key di atas lalu Sync, atau tambah manual.</div>}
        </CardContent>
      </Card>
    </div>
  );
}
