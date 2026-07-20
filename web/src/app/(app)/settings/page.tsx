"use client";
import { useEffect, useState } from "react";
import { Settings2, Wrench, Info, Sparkles, Layers, Droplet, Sticker, Calendar, List, Palette, LayoutGrid, Zap, Save } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Switch } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";

const FEAT_DEFS: Record<string, { labelKey: string; descKey: string; type: "bool" | "text" | "int"; icon: any; group: string }> = {
  feat_enhance_enabled: { labelKey: "feat.enhance", descKey: "feat.enhance_desc", type: "bool", icon: Sparkles, group: "core" },
  enhance_model: { labelKey: "feat.enhance_model", descKey: "feat.enhance_model_desc", type: "text", icon: Sparkles, group: "core" },
  feat_batch_enabled: { labelKey: "feat.batch", descKey: "feat.batch_desc", type: "bool", icon: Layers, group: "core" },
  batch_limit_free: { labelKey: "feat.batch_limit_free", descKey: "feat.batch_limit_free_desc", type: "int", icon: Layers, group: "core" },
  batch_limit_premium: { labelKey: "feat.batch_limit_premium", descKey: "feat.batch_limit_premium_desc", type: "int", icon: Layers, group: "core" },
  feat_watermark_enabled: { labelKey: "feat.watermark", descKey: "feat.watermark_desc", type: "bool", icon: Droplet, group: "core" },
  watermark_text: { labelKey: "feat.watermark_text", descKey: "feat.watermark_text_desc", type: "text", icon: Droplet, group: "core" },
  watermark_free_only: { labelKey: "feat.watermark_free_only", descKey: "feat.watermark_free_only_desc", type: "bool", icon: Droplet, group: "core" },
  feat_sticker_enabled: { labelKey: "feat.sticker", descKey: "feat.sticker_desc", type: "bool", icon: Sticker, group: "core" },
  sticker_max_per_pack: { labelKey: "feat.sticker_max", descKey: "feat.sticker_max_desc", type: "int", icon: Sticker, group: "core" },
  feat_checkin_enabled: { labelKey: "feat.checkin", descKey: "feat.checkin_desc", type: "bool", icon: Calendar, group: "other" },
  feat_inline_enabled: { labelKey: "feat.inline", descKey: "feat.inline_desc", type: "bool", icon: List, group: "other" },
  feat_myworks_enabled: { labelKey: "feat.myworks", descKey: "feat.myworks_desc", type: "bool", icon: LayoutGrid, group: "other" },
  feat_style_enabled: { labelKey: "feat.style", descKey: "feat.style_desc", type: "bool", icon: Palette, group: "other" },
  feat_queue_enabled: { labelKey: "feat.queue", descKey: "feat.queue_desc", type: "bool", icon: Zap, group: "other" },
};

export default function SettingsPage() {
  const { t, lang } = useLang();
  const [limit, setLimit] = useState(20);
  const [maint, setMaint] = useState(false);
  const [info, setInfo] = useState<any>({});
  const [features, setFeatures] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [featLoading, setFeatLoading] = useState(false);

  useEffect(() => {
    api("/api/settings").then((s) => { setLimit(s.daily_limit); setMaint(s.maintenance); setInfo(s); }).catch(() => {});
    api("/api/features").then((f) => setFeatures(f)).catch(() => {});
  }, []);

  async function save() {
    setLoading(true);
    try { await api("/api/settings", { method: "POST", body: JSON.stringify({ daily_limit: Number(limit), maintenance: maint }) }); toast.success(t("settings.saved")); }
    catch { toast.error(t("settings.failed")); } finally { setLoading(false); }
  }
  async function saveFeatures() {
    setFeatLoading(true);
    try { await api("/api/features", { method: "POST", body: JSON.stringify(features) }); toast.success(t("settings.features_saved")); }
    catch { toast.error(t("settings.failed")); } finally { setFeatLoading(false); }
  }

  const groups: Record<string, string[]> = { core: [], other: [] };
  for (const k of Object.keys(FEAT_DEFS)) {
    const g = FEAT_DEFS[k].group;
    if (!groups[g]) groups[g] = [];
    groups[g].push(k);
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("settings.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("settings.sub")}</p>
      </div>

      <Card>
        <CardHeader><CardTitle><Settings2 className="h-4 w-4" />{t("settings.limit_maintenance")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium">{t("settings.daily_limit")}</label>
            <Input type="number" min={0} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
          </div>
          <div className="flex items-center gap-3 border-t pt-4">
            <Wrench className="h-5 w-5 text-amber-500" />
            <div className="flex-1">
              <div className="text-sm font-semibold">{t("settings.maint_mode")}</div>
              <div className="text-xs text-muted-foreground">{t("settings.maint_desc")}</div>
            </div>
            <Switch checked={maint} onChange={setMaint} />
          </div>
        </CardContent>
      </Card>
      <Button onClick={save} disabled={loading}>{loading ? t("settings.saving") : t("settings.save_limit")}</Button>

      <Card>
        <CardHeader><CardTitle><Zap className="h-4 w-4" />{t("settings.feature_control")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-6">
          {Object.entries(groups).map(([gname, keys]) => (
            <div key={gname} className="flex flex-col gap-3">
              <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground border-b pb-1">{t(gname === "core" ? "settings.core_features" : "settings.other_features")}</div>
              {keys.map((k) => {
                const def = FEAT_DEFS[k];
                const val = features[k] ?? "";
                const Icon = def.icon;
                if (def.type === "bool") {
                  return (
                    <div key={k} className="flex items-center gap-3 rounded-lg border p-3">
                      <Icon className="h-5 w-5 text-primary shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold truncate">{t(def.labelKey)}</div>
                        <div className="text-xs text-muted-foreground truncate">{t(def.descKey)}</div>
                        <div className="text-[10px] font-mono text-muted-foreground">{k}</div>
                      </div>
                      <Switch checked={val === "1"} onChange={(v: boolean) => setFeatures((prev) => ({ ...prev, [k]: v ? "1" : "0" }))} />
                    </div>
                  );
                }
                return (
                  <div key={k} className="flex items-center gap-3 rounded-lg border p-3">
                    <Icon className="h-5 w-5 text-muted-foreground shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold">{t(def.labelKey)}</div>
                      <div className="text-xs text-muted-foreground">{t(def.descKey)}</div>
                      <div className="text-[10px] font-mono text-muted-foreground">{k}</div>
                    </div>
                    <Input className="w-36" type={def.type === "int" ? "number" : "text"} value={val} onChange={(e) => setFeatures((prev) => ({ ...prev, [k]: e.target.value }))} />
                  </div>
                );
              })}
            </div>
          ))}
          <Button onClick={saveFeatures} disabled={featLoading} className="mt-2">
            <Save className="h-4 w-4 mr-2" />{featLoading ? t("settings.saving") : t("settings.save_features")}
          </Button>
          <div className="text-xs text-muted-foreground rounded bg-muted p-3">{t("settings.feat_note")}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Info className="h-4 w-4" />{t("settings.info")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm">
          <div className="flex justify-between"><span className="text-muted-foreground">{t("settings.channel_required")}</span><span className="font-medium">{info.channel || "-"}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">{t("settings.model")}</span><span className="font-medium">{info.model}</span></div>
        </CardContent>
      </Card>
    </div>
  );
}
