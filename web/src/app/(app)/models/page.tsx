"use client";
import { useEffect, useState } from "react";
import { Bot, Key, RefreshCw, Power, Star, Trash2, Save, Plus } from "lucide-react";
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
      // init editing state
      const ek: any = {};
      for (const k of keys) {
        ek[k.provider_id] = { key: "", base: k.base_url || "" };
      }
      setEditingKeys((prev) => {
        const merged: any = { ...prev };
        for (const pid of Object.keys(ek)) {
          merged[pid] = { key: "", base: ek[pid]?.base || prev[pid]?.base || "" };
        }
        return merged;
      });
    } catch (e) {
      toast.error("Gagal load data");
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
      setEditingKeys((prev) => ({ ...prev, [pid]: { key: "", base: "" } }));
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
      toast.success(`Synced ${res.synced} models: ${(res.models || []).slice(0, 5).join(", ")}`);
      loadAll();
    } catch (e: any) {
      toast.error(e.message || "Gagal sync — cek API key dulu");
    }
  }

  async function toggleModel(mid: string) {
    try {
      await api(`/api/models/${mid}/toggle`, { method: "POST" });
      loadAll();
    } catch { toast.error("Gagal toggle model"); }
  }

  async function setDefault(mid: string) {
    try {
      await api(`/api/models/${mid}/default`, { method: "POST" });
      toast.success(`Default set ${mid}`);
      loadAll();
    } catch { toast.error("Gagal"); }
  }

  async function deleteModel(mid: string) {
    if (!confirm(`Hapus model ${mid}?`)) return;
    try {
      await api(`/api/models/${mid}`, { method: "DELETE" });
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
      toast.success(`Model ${newModel.id} dibuat`);
      setNewModel({ id: "", provider_id: "rightcodes", display_name: "", description: "", is_active: true });
      loadAll();
    } catch (e: any) {
      toast.error(e.message || "Gagal buat model");
    }
  }

  if (loading) return <div className="p-6">Loading...</div>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2"><Bot className="h-6 w-6" /> Models & Providers</h1>
        <p className="text-sm text-muted-foreground">Atur API key lewat admin (tanpa ubah code), sync model dari Right Codes / Cubence, aktifkan model mana aja. Di bot user cuma lihat nama model, tidak ada nama provider (privasi).</p>
      </div>

      <Card>
        <CardHeader><CardTitle><Key className="h-4 w-4" /> API Keys (Edit via Admin)</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          {apikeys.map((k) => (
            <div key={k.provider_id} className="rounded-lg border p-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold uppercase">{k.provider_id}</div>
                  <div className="text-xs text-muted-foreground">Key: {k.masked || "belum di-set"} {k.has_key ? "✅" : "❌"} | Len {k.api_key_length} | Base: {k.base_url || "-"}</div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => syncModels(k.provider_id)}><RefreshCw className="h-4 w-4 mr-1" /> Sync Models</Button>
                  <Button size="sm" variant="outline" onClick={() => toggleProvider(k.provider_id)}><Power className="h-4 w-4 mr-1" /> Toggle</Button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div>
                  <label className="text-xs">API Key baru (kosongkan jika tidak ubah)</label>
                  <Input type="password" placeholder="sk-..." value={editingKeys[k.provider_id]?.key || ""} onChange={(e) => setEditingKeys((p) => ({ ...p, [k.provider_id]: { ...(p[k.provider_id] || { key: "", base: "" }), key: e.target.value } }))} />
                </div>
                <div>
                  <label className="text-xs">Base URL</label>
                  <Input placeholder="https://www.right.codes/draw" value={editingKeys[k.provider_id]?.base ?? k.base_url} onChange={(e) => setEditingKeys((p) => ({ ...p, [k.provider_id]: { ...(p[k.provider_id] || { key: "", base: "" }), base: e.target.value } }))} />
                </div>
              </div>
              <Button size="sm" onClick={() => saveApiKey(k.provider_id)}><Save className="h-4 w-4 mr-1" /> Simpan Key</Button>
            </div>
          ))}
          <div className="text-xs text-muted-foreground bg-muted p-2 rounded">Right Codes base default: https://www.right.codes/draw — task polling otomatis di https://www.right.codes/v1/tasks/&#123;task_id&#125; (site-level). Cubence default: https://api-dmit.cubence.com — sync butuh API key valid.</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Bot className="h-4 w-4" /> Providers Status</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2">
          {providers.map((p) => (
            <div key={p.id} className="flex items-center justify-between border rounded p-3">
              <div>
                <div className="font-medium">{p.id} {p.is_active ? "🟢 Active" : "🔴 Inactive"}</div>
                <div className="text-xs text-muted-foreground">{p.base_url} | key {p.api_key_masked || "—"}</div>
              </div>
              <Switch checked={p.is_active} onChange={() => toggleProvider(p.id)} />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Plus className="h-4 w-4" /> Tambah Model Manual</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="model id (e.g. nano-banana-fast)" value={newModel.id} onChange={(e) => setNewModel((p) => ({ ...p, id: e.target.value }))} />
            <Input placeholder="Display name (user-facing, no provider)" value={newModel.display_name} onChange={(e) => setNewModel((p) => ({ ...p, display_name: e.target.value }))} />
            <select className="border rounded px-2 py-2 text-sm bg-background" value={newModel.provider_id} onChange={(e) => setNewModel((p) => ({ ...p, provider_id: e.target.value }))}>
              <option value="rightcodes">rightcodes (Right Codes)</option>
              <option value="cubence">cubence (Cubence)</option>
            </select>
            <Input placeholder="Description optional" value={newModel.description} onChange={(e) => setNewModel((p) => ({ ...p, description: e.target.value }))} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs">Aktif</span><Switch checked={newModel.is_active} onChange={(v: boolean) => setNewModel((p) => ({ ...p, is_active: v }))} />
            <Button size="sm" onClick={createModel}><Plus className="h-4 w-4 mr-1" /> Buat Model</Button>
          </div>
          <div className="text-xs text-muted-foreground">ID harus akurat sesuai Right Codes (contoh: nano-banana-fast, flux-pro, gpt-image-2-vip, etc). Cek di dashboard Right Codes → Channels & Models. User di bot hanya lihat Display Name, tidak tau provider.</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Models List ({models.length}) — Toggle Active per Model</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 max-h-[700px] overflow-auto">
          {models.map((m) => (
            <div key={m.id} className="flex items-center gap-3 border rounded p-3">
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{m.display_name} {m.is_default ? "⭐" : ""} {m.is_active ? "🟢" : "⚪"}</div>
                <div className="text-xs font-mono truncate">ID: {m.id} | Provider: {m.provider_id} {m.provider_active ? "" : "(provider OFF)"} | {m.is_default ? "Default" : ""}</div>
                <div className="text-[11px] text-muted-foreground truncate">{m.description || "-"}</div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button size="sm" variant="outline" onClick={() => setDefault(m.id)} title="Set default"><Star className="h-4 w-4" /></Button>
                <Switch checked={m.is_active} onChange={() => toggleModel(m.id)} />
                <Button size="sm" variant="ghost" onClick={() => deleteModel(m.id)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            </div>
          ))}
          {models.length === 0 && <div className="text-sm text-muted-foreground">Belum ada model — sync dari provider atau tambah manual. Pastikan API key Right Codes sudah diisi di atas lalu klik Sync.</div>}
        </CardContent>
      </Card>
    </div>
  );
}
