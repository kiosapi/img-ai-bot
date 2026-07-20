"use client";
import { useEffect, useMemo, useState } from "react";
import { FileText, Save, Search, Sparkles, AlertTriangle, Gift, Wallet, Crown, Users, Calendar, ImageIcon, Palette, ShieldAlert, Layers, Eye, X, RefreshCw, Trash2, Info, Check } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Badge } from "@/components/ui/controls";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CustomSelect } from "@/components/ui/modal";
import { useLang } from "@/lib/i18n";

type DynamicText = {
  key: string;
  value: string;
  description: string;
  group: string;
  is_set: boolean;
};

const GROUP_ICONS: Record<string, any> = {
  Welcome: Sparkles,
  Help: Info,
  Errors: AlertTriangle,
  Checkin: Calendar,
  Referral: Gift,
  Premium: Crown,
  Balance: Wallet,
  Subscription: Users,
  Features: ShieldAlert,
  Inline: ImageIcon,
  Custom: FileText,
  Other: Layers,
};

const GROUP_ORDER = ["Welcome", "Help", "Errors", "Checkin", "Referral", "Premium", "Balance", "Subscription", "Features", "Inline", "Custom", "Other"];

export default function TextsPage() {
  const { t } = useLang();
  const [texts, setTexts] = useState<DynamicText[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [activeGroup, setActiveGroup] = useState<string>("All");
  const [filterSet, setFilterSet] = useState<"all" | "set" | "empty">("all");
  const [previewKey, setPreviewKey] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api("/api/texts");
      setTexts(r.texts || []);
    } catch (e: any) {
      toast.error(e.message || "Gagal load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const groups = useMemo(() => {
    const set = new Set(texts.map((x) => x.group));
    const ordered = GROUP_ORDER.filter((g) => set.has(g));
    const extra = [...set].filter((g) => !GROUP_ORDER.includes(g)).sort();
    return ["All", ...ordered, ...extra];
  }, [texts]);

  const filtered = useMemo(() => {
    let arr = texts;
    if (activeGroup !== "All") arr = arr.filter((x) => x.group === activeGroup);
    if (filterSet === "set") arr = arr.filter((x) => x.is_set);
    if (filterSet === "empty") arr = arr.filter((x) => !x.is_set);
    if (search.trim()) {
      const q = search.toLowerCase();
      arr = arr.filter((x) => x.key.toLowerCase().includes(q) || x.value.toLowerCase().includes(q) || x.description.toLowerCase().includes(q) || x.group.toLowerCase().includes(q));
    }
    return arr;
  }, [texts, activeGroup, filterSet, search]);

  const groupedView = useMemo(() => {
    if (activeGroup !== "All") return { [activeGroup]: filtered };
    const map: Record<string, DynamicText[]> = {};
    for (const item of filtered) {
      if (!map[item.group]) map[item.group] = [];
      map[item.group].push(item);
    }
    return map;
  }, [filtered, activeGroup]);

  const updateLocal = (key: string, value: string) => {
    setTexts((prev) => prev.map((p) => (p.key === key ? { ...p, value, is_set: Boolean(value.trim()) } : p)));
  };

  const save = async (key: string) => {
    const item = texts.find((x) => x.key === key);
    if (!item) return;
    setSavingKey(key);
    try {
      await api("/api/texts", { method: "POST", body: JSON.stringify({ key, value: item.value }) });
      toast.success(t("texts.saved") || "Saved");
      // mark set instantly
      setTexts((prev) => prev.map((p) => (p.key === key ? { ...p, is_set: Boolean(item.value.trim()) } : p)));
    } catch (e: any) {
      toast.error(e.message || "Gagal simpan");
    } finally {
      setSavingKey(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api(`/api/texts/${deleteTarget}`, { method: "DELETE" });
      toast.success(t("texts.deleted") || "Deleted — fallback active");
      await load();
    } catch (e: any) {
      toast.error(e.message || "Gagal hapus");
    } finally {
      setDeleteTarget(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        <div className="h-8 w-40 animate-pulse rounded bg-muted" />
        <div className="h-20 rounded bg-muted" />
        <div className="grid gap-4">
          {[1, 2, 3].map((i) => (<div key={i} className="h-32 animate-pulse rounded-lg border bg-muted/50" />))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <FileText className="h-6 w-6 text-primary" />
            {t("texts.title") || "Dynamic Texts"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">{t("texts.sub") || "Kelola semua teks bot tanpa ubah kode — edit welcome, help, error, referral, premium, dsb. Support markdown HTML."}</p>
        </div>
        <Button variant="outline" size="sm" onClick={load}><RefreshCw className="h-4 w-4" /> {t("common.refresh") || "Refresh"}</Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card><CardContent className="pt-4"><div className="text-2xl font-bold">{texts.length}</div><div className="text-xs text-muted-foreground">{t("texts.total") || "Total Keys"}</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-2xl font-bold text-emerald-500">{texts.filter((x) => x.is_set).length}</div><div className="text-xs text-muted-foreground">{t("texts.customized") || "Customized"}</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-2xl font-bold text-amber-500">{texts.filter((x) => !x.is_set).length}</div><div className="text-xs text-muted-foreground">{t("texts.using_default") || "Default Fallback"}</div></CardContent></Card>
        <Card><CardContent className="pt-4"><div className="text-2xl font-bold">{new Set(texts.map((x) => x.group)).size}</div><div className="text-xs text-muted-foreground">{t("texts.groups") || "Groups"}</div></CardContent></Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4 flex flex-col gap-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center justify-between">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input className="pl-9" placeholder={t("texts.search_ph") || "Cari key, value, description..."} value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <div className="flex items-center gap-2">
              <CustomSelect value={filterSet} onChange={(v)=>setFilterSet(v as any)} options={[{value:"all",label:t("texts.filter_all")||"Semua"},{value:"set",label:t("texts.filter_set")||"Sudah di-set"},{value:"empty",label:t("texts.filter_empty")||"Masih default"}]} className="w-[150px]" />
              <Badge variant="muted">{filtered.length} / {texts.length}</Badge>
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {groups.map((g) => {
              const active = activeGroup === g;
              const Icon = GROUP_ICONS[g] || FileText;
              return (
                <button key={g} onClick={() => setActiveGroup(g)}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${active ? "bg-primary text-primary-foreground border-primary" : "bg-card hover:bg-accent"}`}>
                  {g !== "All" && <Icon className="h-3.5 w-3.5" />} {g === "All" ? (t("texts.all_groups") || "All") : g}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* List by group */}
      <div className="flex flex-col gap-6">
        {Object.entries(groupedView).map(([groupName, items]) => {
          const Icon = GROUP_ICONS[groupName] || FileText;
          if (items.length === 0) return null;
          return (
            <div key={groupName} className="flex flex-col gap-3">
              {activeGroup === "All" && (
                <div className="flex items-center gap-2 px-1">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-semibold tracking-wide uppercase text-muted-foreground">{groupName}</span>
                  <Badge variant="muted" className="ml-2">{items.length}</Badge>
                </div>
              )}
              <div className="grid gap-4">
                {items.map((item) => {
                  const isPreview = previewKey === item.key;
                  return (
                    <Card key={item.key} className={item.is_set ? "border-emerald-500/30" : ""}>
                      <CardHeader className="pb-2">
                        <CardTitle className="flex items-start justify-between gap-2 normal-case">
                          <div className="flex flex-col gap-1 min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <code className="rounded bg-muted px-2 py-0.5 text-sm font-mono">{item.key}</code>
                              {item.is_set ? <Badge variant="success"><Check className="h-3 w-3" /> set</Badge> : <Badge variant="muted">default</Badge>}
                              <Badge variant="muted" className="font-normal">{item.group}</Badge>
                            </div>
                            <span className="text-xs text-muted-foreground font-normal normal-case tracking-normal">{item.description}</span>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <Button size="sm" variant="ghost" onClick={() => setPreviewKey(isPreview ? null : item.key)}>
                              {isPreview ? <X className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                            {item.is_set && (
                              <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={() => setDeleteTarget(item.key)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="flex flex-col gap-3">
                        <div className="relative">
                          <Textarea
                            value={item.value}
                            onChange={(e) => updateLocal(item.key, e.target.value)}
                            placeholder={t("texts.placeholder") || `Kosong = pakai default bawaan bot. Support {placeholders}, HTML <b>, <i>, <code>.`}
                            className="min-h-[84px] font-mono text-sm"
                            rows={item.value.length > 120 ? 4 : 2}
                            style={{ height: "auto", minHeight: item.value.length > 200 ? "120px" : "72px" }}
                            onInput={(e) => {
                              const target = e.target as HTMLTextAreaElement;
                              target.style.height = "auto";
                              target.style.height = target.scrollHeight + "px";
                            }}
                          />
                          <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                            <span>{item.value.length} chars</span>
                            {item.value.includes("{") && <span className="flex items-center gap-1"><Palette className="h-3 w-3" /> placeholders detected</span>}
                          </div>
                        </div>

                        {isPreview && item.value && (
                          <div className="rounded-md border bg-muted/40 p-3">
                            <div className="mb-1 flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"><Eye className="h-3 w-3" /> Preview (rendered as bot would show — HTML-ish)</div>
                            <div className="whitespace-pre-wrap text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: item.value.replaceAll("<b>", "<strong>").replaceAll("</b>", "</strong>").replaceAll("<i>", "<em>").replaceAll("</i>", "</em>").replaceAll("\n", "<br/>") }} />
                          </div>
                        )}

                        <div className="flex gap-2">
                          <Button size="sm" onClick={() => save(item.key)} disabled={savingKey === item.key} className="min-w-24">
                            <Save className="h-4 w-4" /> {savingKey === item.key ? (t("common.saving") || "Saving...") : (t("common.save") || "Save")}
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => updateLocal(item.key, "")} disabled={!item.value}>{t("common.clear") || "Clear"}</Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">{t("texts.no_results") || "Tidak ada hasil — coba ubah filter/search"}</CardContent></Card>
        )}
      </div>

      <Card>
        <CardHeader><CardTitle><Info className="h-4 w-4" /> {t("texts.how_title") || "Cara Pakai"}</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm text-muted-foreground leading-relaxed">
          <p>{t("texts.how_1") || "Kosong = bot pakai fallback default (i18n.py / hardcoded). Isi = override instant tanpa restart."}</p>
          <p>{t("texts.how_2") || "Support placeholder seperti {name}, {brand}, {used}, {limit}, {err}, {link}, dll — biarkan jika tidak tahu."}</p>
          <p>{t("texts.how_3") || "Support HTML Telegram <b>, <i>, <code>, <u>. Jangan pakai <script> atau javascript: — akan diblokir."}</p>
          <p>{t("texts.how_4") || "Setelah Save, efek langsung — tidak perlu restart bot (dibaca via db.get_setting tiap request)."}</p>
        </CardContent>
      </Card>

      <ConfirmDialog open={deleteTarget !== null} onClose={() => setDeleteTarget(null)} onConfirm={handleDelete} variant="destructive"
        title={t("texts.delete_title") || "Hapus custom text?"} confirmLabel={t("common.yes_delete") || "Ya, Hapus"}
        description={<>Hapus <code className="bg-muted px-1 rounded">{deleteTarget}</code>? Bot akan balik ke default bawaan. Tidak bisa dibatalkan.</>} />
    </div>
  );
}
