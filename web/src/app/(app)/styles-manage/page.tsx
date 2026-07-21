"use client";
import { useEffect, useState, useMemo } from "react";
import { Palette, Plus, Edit3, Trash2, Search, Power, ArrowUpDown, Image as ImageIcon, Tag, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Textarea, Badge, Switch } from "@/components/ui/controls";
import { Modal, Field, CustomSelect } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useLang } from "@/lib/i18n";
import { PageLoader } from "@/components/ui/page-loader";

type StyleItem = {
  id: number;
  code: string;
  name: string;
  prompt_prefix: string;
  thumbnail_url: string | null;
  category: string;
  is_active: boolean;
  sort_order: number;
  created_at: string;
};

const CATEGORY_OPTIONS = [
  { value: "general", label: "General" },
  { value: "anime", label: "Anime" },
  { value: "photo", label: "Photo" },
  { value: "fantasy", label: "Fantasy" },
  { value: "artistic", label: "Artistic" },
  { value: "realistic", label: "Realistic" },
  { value: "portrait", label: "Portrait" },
  { value: "landscape", label: "Landscape" },
  { value: "other", label: "Other" },
];

const emptyForm = {
  id: 0,
  code: "",
  name: "",
  prompt_prefix: "",
  thumbnail_url: "",
  category: "general",
  is_active: true,
  sort_order: 0,
};

export default function StylesManagePage() {
  const { t, lang } = useLang();
  const [styles, setStyles] = useState<StyleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [catFilter, setCatFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState(""); // "", true, false
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<typeof emptyForm>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [delTarget, setDelTarget] = useState<StyleItem | null>(null);
  const [categories, setCategories] = useState<string[]>([]);

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (catFilter) params.set("category", catFilter);
      if (activeFilter) params.set("active", activeFilter);
      const qs = params.toString();
      const data = await api(`/api/styles/list${qs ? `?${qs}` : ""}`);
      setStyles(data.styles || []);
      // also fetch categories list (if no filter, derive)
      try {
        const catData = await api("/api/styles/categories");
        if (catData.categories) setCategories(catData.categories);
      } catch {}
    } catch (e: any) {
      toast.error(e.message || "Gagal memuat styles");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const h = setTimeout(() => load(), 300);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, catFilter, activeFilter]);

  function openNew() {
    setForm({ ...emptyForm, sort_order: styles.length });
    setOpen(true);
  }

  function openEdit(s: StyleItem) {
    setForm({
      id: s.id,
      code: s.code,
      name: s.name,
      prompt_prefix: s.prompt_prefix || "",
      thumbnail_url: s.thumbnail_url || "",
      category: s.category || "general",
      is_active: s.is_active,
      sort_order: s.sort_order,
    });
    setOpen(true);
  }

  async function save() {
    // validations mirroring backend
    const codeRe = /^[a-z0-9_-]{1,30}$/;
    if (!codeRe.test(form.code.trim().toLowerCase())) {
      toast.error(lang === "id" ? "Code harus a-z 0-9 _- 1-30 huruf kecil" : "Code must match ^[a-z0-9_-]{1,30}$");
      return;
    }
    if (!form.name.trim()) {
      toast.error(lang === "id" ? "Nama wajib" : "Name required");
      return;
    }
    if (form.name.trim().length > 100) {
      toast.error("Name max 100");
      return;
    }
    if ((form.prompt_prefix || "").length > 500) {
      toast.error("Prompt max 500");
      return;
    }
    setSaving(true);
    try {
      const payload: any = {
        code: form.code.trim().toLowerCase(),
        name: form.name.trim(),
        prompt_prefix: (form.prompt_prefix || "").trim(),
        thumbnail_url: form.thumbnail_url.trim() || null,
        category: (form.category || "general").trim().toLowerCase(),
        is_active: form.is_active,
        sort_order: Number(form.sort_order) || 0,
      };
      if (form.id) {
        await api(`/api/styles/${form.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success(lang === "id" ? "Style diperbarui" : "Style updated");
      } else {
        await api("/api/styles", { method: "POST", body: JSON.stringify(payload) });
        toast.success(lang === "id" ? "Style dibuat" : "Style created");
      }
      setOpen(false);
      load();
    } catch (e: any) {
      toast.error(e.message || "Gagal simpan");
    } finally {
      setSaving(false);
    }
  }

  async function doDelete() {
    if (!delTarget) return;
    try {
      await api(`/api/styles/${delTarget.id}`, { method: "DELETE" });
      toast.success(lang === "id" ? "Style dihapus" : "Style deleted");
      setDelTarget(null);
      load();
    } catch (e: any) {
      toast.error(e.message || "Gagal hapus");
    }
  }

  async function toggleActive(s: StyleItem) {
    try {
      await api(`/api/styles/${s.id}/toggle`, { method: "PATCH" });
      toast.success(`${s.code} ${s.is_active ? "dinonaktifkan" : "diaktifkan"}`);
      // optimistic
      setStyles((prev) => prev.map((x) => (x.id === s.id ? { ...x, is_active: !x.is_active } : x)));
    } catch (e: any) {
      toast.error(e.message || "Gagal toggle");
    }
  }

  const filteredCategories = useMemo(() => {
    const set = new Set<string>(categories);
    styles.forEach((s) => set.add(s.category));
    return Array.from(set).sort();
  }, [categories, styles]);

  return (
    <div className="flex flex-col gap-4 md:gap-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2">
            <Palette className="h-5 w-5 md:h-6 md:w-6" /> {t("nav.styles_manage")}
          </h1>
          <p className="text-xs md:text-sm text-muted-foreground">
            {lang === "id"
              ? "Kelola preset gaya visual tanpa edit code — grid gallery, thumbnail, pencarian, toggle, reorder."
              : "Manage visual style presets without code — gallery, thumbnail, search, toggle, reorder."}
          </p>
        </div>
        <Button onClick={openNew} className="w-full md:w-auto">
          <Plus className="h-4 w-4" /> {lang === "id" ? "Tambah Style" : "Add Style"}
        </Button>
      </div>

      <Card>
        <CardContent className="pt-4 flex flex-col gap-3">
          <div className="flex flex-col md:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder={lang === "id" ? "Cari nama / code / kategori / prompt..." : "Search name / code / category / prompt..."}
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <div className="flex gap-2 flex-wrap">
              <div className="w-[150px]">
                <CustomSelect
                  value={catFilter}
                  onChange={setCatFilter}
                  placeholder={lang === "id" ? "Kategori" : "Category"}
                  options={[{ value: "", label: lang === "id" ? "Semua Kategori" : "All Categories" }, ...filteredCategories.map((c) => ({ value: c, label: c }))]}
                />
              </div>
              <div className="w-[150px]">
                <CustomSelect
                  value={activeFilter}
                  onChange={setActiveFilter}
                  placeholder="Status"
                  options={[
                    { value: "", label: lang === "id" ? "Semua Status" : "All Status" },
                    { value: "true", label: lang === "id" ? "Aktif" : "Active" },
                    { value: "false", label: lang === "id" ? "Non-aktif" : "Inactive" },
                  ]}
                />
              </div>
              <Button variant="outline" size="sm" onClick={() => { setQ(""); setCatFilter(""); setActiveFilter(""); }} className="shrink-0">
                Reset
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <PageLoader label={t("common.loading")} cards={3} rows={3} />
      ) : styles.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground flex flex-col items-center gap-2">
            <Palette className="h-8 w-8 opacity-50" />
            {lang === "id" ? "Belum ada style preset. Tambah dari tombol di atas." : "No style presets yet. Add from button above."}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 md:gap-4">
          {styles.map((s) => (
            <Card key={s.id} className={`overflow-hidden group hover:shadow-lg transition-all ${!s.is_active ? "opacity-60" : ""}`}>
              <div className="relative aspect-[4/3] w-full bg-muted flex items-center justify-center overflow-hidden">
                {s.thumbnail_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={s.thumbnail_url} alt={s.name} className="h-full w-full object-cover group-hover:scale-[1.03] transition-transform" loading="lazy" />
                ) : (
                  <div className="flex flex-col items-center justify-center gap-1 text-muted-foreground p-3">
                    <ImageIcon className="h-8 w-8 opacity-40" />
                    <span className="text-[11px] text-center line-clamp-2">{s.name}</span>
                  </div>
                )}
                <div className="absolute top-2 left-2 flex gap-1.5">
                  <Badge variant={s.is_active ? "success" : "muted"} className="text-[10px] px-1.5 py-0">
                    {s.is_active ? (lang === "id" ? "Aktif" : "Active") : lang === "id" ? "Non-aktif" : "Inactive"}
                  </Badge>
                  <Badge variant="default" className="text-[10px] px-1.5 py-0">{s.category}</Badge>
                </div>
                <div className="absolute top-2 right-2 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded font-mono">#{s.sort_order}</div>
              </div>
              <CardContent className="pt-3 pb-3 px-3 flex flex-col gap-2">
                <div>
                  <div className="font-semibold text-sm truncate flex items-center gap-1.5">
                    {s.name}
                    <span className="text-[10px] font-mono font-normal text-muted-foreground truncate">({s.code})</span>
                  </div>
                  {s.prompt_prefix ? (
                    <div className="text-[11px] text-muted-foreground line-clamp-2 mt-1" title={s.prompt_prefix}>
                      {s.prompt_prefix}
                    </div>
                  ) : (
                    <div className="text-[11px] text-muted-foreground italic mt-1">{lang === "id" ? "Tanpa prompt suffix" : "No prompt suffix"}</div>
                  )}
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  <div className="flex items-center gap-1 flex-1 min-w-0">
                    <Tag className="h-3 w-3 text-muted-foreground shrink-0" />
                    <span className="text-[11px] truncate">{s.category}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button size="sm" variant="outline" className="h-7 w-7 p-0" onClick={() => openEdit(s)} title={t("common.edit")}>
                      <Edit3 className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="sm" variant="outline" className="h-7 w-7 p-0" onClick={() => toggleActive(s)} title={lang === "id" ? "Toggle aktif" : "Toggle active"}>
                      <Power className={`h-3.5 w-3.5 ${s.is_active ? "text-emerald-600" : "text-muted-foreground"}`} />
                    </Button>
                    <Button size="sm" variant="destructive" className="h-7 w-7 p-0" onClick={() => setDelTarget(s)} title={t("common.delete")}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  <Settings2 className="h-3 w-3 text-muted-foreground" />
                  <span className="text-[11px] text-muted-foreground">ID {s.id} | sort {s.sort_order}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add/Edit Modal */}
      <Modal open={open} onClose={() => setOpen(false)} title={form.id ? (lang === "id" ? "Edit Style" : "Edit Style") : (lang === "id" ? "Tambah Style" : "Add Style")}>
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Code (slug) * — regex ^[a-z0-9_-]{1,30}$">
              <Input
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value.toLowerCase() })}
                placeholder="anime, ghibli, realistic..."
                maxLength={30}
              />
            </Field>
            <Field label={lang === "id" ? "Kategori" : "Category"}>
              <CustomSelect
                value={form.category}
                onChange={(v) => setForm({ ...form, category: v })}
                options={CATEGORY_OPTIONS}
                placeholder="general"
              />
            </Field>
          </div>
          <Field label={lang === "id" ? "Nama Tampilan (max 100) *" : "Display Name (max 100) *"}>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={lang === "id" ? "Anime, Ghibli, Realistis..." : "Anime, Ghibli, Realistic..."} maxLength={100} />
          </Field>
          <Field label={lang === "id" ? "Prompt Suffix / Prefix (max 500) — ditambah ke prompt user" : "Prompt Suffix/Prefix (max 500)"}>
            <Textarea value={form.prompt_prefix} onChange={(e) => setForm({ ...form, prompt_prefix: e.target.value })} placeholder="anime style, vibrant colors, detailed" maxLength={500} rows={3} />
            <div className="mt-1 text-[11px] text-muted-foreground">{form.prompt_prefix.length}/500</div>
          </Field>
          <Field label={lang === "id" ? "Thumbnail URL (https, opsional)" : "Thumbnail URL (https, optional)"}>
            <Input value={form.thumbnail_url} onChange={(e) => setForm({ ...form, thumbnail_url: e.target.value })} placeholder="https://.../preview.jpg" maxLength={500} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Sort Order (0 = atas)">
              <Input type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: parseInt(e.target.value) || 0 })} min={0} max={10000} />
            </Field>
            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">{lang === "id" ? "Status Aktif" : "Active Status"}</span>
              <div className="flex items-center gap-2 h-10">
                <Switch checked={form.is_active} onChange={(v) => setForm({ ...form, is_active: v })} />
                <span className="text-xs text-muted-foreground">{form.is_active ? (lang === "id" ? "Muncul di bot" : "Visible in bot") : (lang === "id" ? "Disembunyikan" : "Hidden")}</span>
              </div>
            </div>
          </div>
          {form.thumbnail_url ? (
            <div className="rounded-lg border p-2 bg-muted/30">
              <div className="text-[11px] text-muted-foreground mb-1 flex items-center gap-1"><ImageIcon className="h-3 w-3" /> Preview</div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={form.thumbnail_url} alt="preview" className="max-h-40 rounded object-cover w-full" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
            </div>
          ) : null}
          <Button className="w-full mt-2" onClick={save} disabled={saving}>
            {saving ? (lang === "id" ? "Menyimpan..." : "Saving...") : lang === "id" ? "Simpan Style" : "Save Style"}
          </Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={delTarget !== null}
        onClose={() => setDelTarget(null)}
        onConfirm={doDelete}
        variant="destructive"
        title={lang === "id" ? "Hapus Style Preset" : "Delete Style Preset"}
        confirmLabel={t("common.yes_delete")}
        description={<>{lang === "id" ? `Yakin hapus style "${delTarget?.name}" (${delTarget?.code})? Tidak bisa batal.` : `Delete style "${delTarget?.name}" (${delTarget?.code})? Cannot undo.`}</>}
      />
    </div>
  );
}
