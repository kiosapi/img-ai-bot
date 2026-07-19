"use client";
import { useEffect, useState } from "react";
import { Settings2, Wrench, Info, Sparkles, Layers, Droplet, Sticker, Calendar, List, Palette, LayoutGrid, Zap, Save } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Switch } from "@/components/ui/controls";

const FEAT_DEFS: Record<string, { label: string; desc: string; type: "bool" | "text" | "int"; icon: any; group: string }> = {
  feat_enhance_enabled: { label: "Prompt Enhance", desc: "Tombol enhance prompt via LLM (fitur 10)", type: "bool", icon: Sparkles, group: "Fitur Inti" },
  enhance_model: { label: "Model Enhance", desc: "Model OpenAI-compatible untuk enhance (default gpt-4o-mini)", type: "text", icon: Sparkles, group: "Fitur Inti" },
  feat_batch_enabled: { label: "Batch Generate", desc: "Generate multiple variasi sekaligus (fitur 14)", type: "bool", icon: Layers, group: "Fitur Inti" },
  batch_limit_free: { label: "Batch Limit Free", desc: "Max batch untuk user free", type: "int", icon: Layers, group: "Fitur Inti" },
  batch_limit_premium: { label: "Batch Limit Premium", desc: "Max batch untuk premium", type: "int", icon: Layers, group: "Fitur Inti" },
  feat_watermark_enabled: { label: "Watermark", desc: "Tambah watermark text ke caption + overlay gambar (fitur 15)", type: "bool", icon: Droplet, group: "Fitur Inti" },
  watermark_text: { label: "Watermark Text", desc: "Text watermark (caption + gambar)", type: "text", icon: Droplet, group: "Fitur Inti" },
  watermark_free_only: { label: "Watermark Free Only", desc: "ON = premium bebas watermark, OFF = semua kena watermark", type: "bool", icon: Droplet, group: "Fitur Inti" },
  feat_sticker_enabled: { label: "Sticker Pack", desc: "Buat sticker Telegram dari karya (fitur 17)", type: "bool", icon: Sticker, group: "Fitur Inti" },
  sticker_max_per_pack: { label: "Sticker Max per Pack", desc: "Maks sticker per pack", type: "int", icon: Sticker, group: "Fitur Inti" },
  feat_checkin_enabled: { label: "Daily Check-in", desc: "Check-in harian streak (fitur 6)", type: "bool", icon: Calendar, group: "Fitur Lain" },
  feat_inline_enabled: { label: "Inline Mode", desc: "Gallery inline @bot (fitur 7)", type: "bool", icon: List, group: "Fitur Lain" },
  feat_myworks_enabled: { label: "My Works / History", desc: "History karya user (fitur 2)", type: "bool", icon: LayoutGrid, group: "Fitur Lain" },
  feat_style_enabled: { label: "Style Presets", desc: "Preset gaya visual (fitur 3)", type: "bool", icon: Palette, group: "Fitur Lain" },
  feat_queue_enabled: { label: "Anti-Spam Queue", desc: "Batas 1 job per user (fitur 9)", type: "bool", icon: Zap, group: "Fitur Lain" },
};

export default function SettingsPage() {
  const [limit, setLimit] = useState(20);
  const [maint, setMaint] = useState(false);
  const [info, setInfo] = useState<any>({});
  const [features, setFeatures] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [featLoading, setFeatLoading] = useState(false);

  useEffect(() => {
    api("/api/settings").then((s) => {
      setLimit(s.daily_limit); setMaint(s.maintenance); setInfo(s);
    }).catch(() => {});
    api("/api/features").then((f) => setFeatures(f)).catch(() => {});
  }, []);

  async function save() {
    setLoading(true);
    try {
      await api("/api/settings", { method: "POST", body: JSON.stringify({ daily_limit: Number(limit), maintenance: maint }) });
      toast.success("Pengaturan disimpan");
    } catch { toast.error("Gagal menyimpan"); }
    finally { setLoading(false); }
  }

  async function saveFeatures() {
    setFeatLoading(true);
    try {
      await api("/api/features", { method: "POST", body: JSON.stringify(features) });
      toast.success("Fitur disimpan - berlaku instant tanpa restart");
    } catch { toast.error("Gagal simpan fitur"); }
    finally { setFeatLoading(false); }
  }

  const groups: Record<string, string[]> = {};
  for (const k of Object.keys(FEAT_DEFS)) {
    const g = FEAT_DEFS[k].group;
    if (!groups[g]) groups[g] = [];
    groups[g].push(k);
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Pengaturan & Fitur</h1>
        <p className="text-sm text-muted-foreground">Kelola bot tanpa ubah code - toggle instant, berlaku langsung</p>
      </div>

      <Card>
        <CardHeader><CardTitle><Settings2 className="h-4 w-4" />Limit & Maintenance</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium">Limit Harian per User</label>
            <Input type="number" min={0} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
          </div>
          <div className="flex items-center gap-3 border-t pt-4">
            <Wrench className="h-5 w-5 text-amber-500" />
            <div className="flex-1">
              <div className="text-sm font-semibold">Mode Maintenance</div>
              <div className="text-xs text-muted-foreground">Blokir semua user (kecuali admin) - butuh global middleware</div>
            </div>
            <Switch checked={maint} onChange={setMaint} />
          </div>
        </CardContent>
      </Card>
      <Button onClick={save} disabled={loading}>{loading ? "Menyimpan..." : "Simpan Limit & Maintenance"}</Button>

      <Card>
        <CardHeader><CardTitle><Zap className="h-4 w-4" />Kontrol Fitur Lengkap (Tanpa Code)</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-6">
          {Object.entries(groups).map(([gname, keys]) => (
            <div key={gname} className="flex flex-col gap-3">
              <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground border-b pb-1">{gname}</div>
              {keys.map((k) => {
                const def = FEAT_DEFS[k];
                const val = features[k] ?? "";
                const Icon = def.icon;
                if (def.type === "bool") {
                  return (
                    <div key={k} className="flex items-center gap-3 rounded-lg border p-3">
                      <Icon className="h-5 w-5 text-primary shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold truncate">{def.label}</div>
                        <div className="text-xs text-muted-foreground truncate">{def.desc}</div>
                        <div className="text-[10px] font-mono text-muted-foreground">{k}</div>
                      </div>
                      <Switch
                        checked={val === "1"}
                        onChange={(v: boolean) => setFeatures((prev) => ({ ...prev, [k]: v ? "1" : "0" }))}
                      />
                    </div>
                  );
                }
                return (
                  <div key={k} className="flex items-center gap-3 rounded-lg border p-3">
                    <Icon className="h-5 w-5 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold">{def.label}</div>
                      <div className="text-xs text-muted-foreground">{def.desc}</div>
                      <div className="text-[10px] font-mono text-muted-foreground">{k}</div>
                    </div>
                    <Input
                      className="w-36"
                      type={def.type === "int" ? "number" : "text"}
                      value={val}
                      onChange={(e) => setFeatures((prev) => ({ ...prev, [k]: e.target.value }))}
                    />
                  </div>
                );
              })}
            </div>
          ))}
          <Button onClick={saveFeatures} disabled={featLoading} className="mt-2">
            <Save className="h-4 w-4 mr-2" />{featLoading ? "Menyimpan..." : "Simpan Semua Fitur (Instant)"}
          </Button>
          <div className="text-xs text-muted-foreground rounded bg-muted p-3">
            Semua toggle berlaku instant tanpa restart bot. Bot baca settings dari DB tiap request via feature_flags. Matikan fitur jika perlu maintenance fitur spesifik.
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Info className="h-4 w-4" />Info</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm">
          <div className="flex justify-between"><span className="text-muted-foreground">Channel Wajib</span><span className="font-medium">{info.channel || "-"}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Model</span><span className="font-medium">{info.model}</span></div>
        </CardContent>
      </Card>
    </div>
  );
}
