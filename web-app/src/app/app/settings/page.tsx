"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell";
import { PageLoader } from "@/components/page-loader";
import { api, getToken, setToken, type Me } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

export default function SettingsPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const lang: Lang = (me?.lang as Lang) || "id";

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    api<Me>("/api/user/me")
      .then(setMe)
      .catch(() => router.replace("/"));
  }, [router]);

  async function save(patch: { lang?: Lang; gallery_public?: boolean }) {
    setMsg(null);
    try {
      await api("/api/user/me", { method: "PATCH", body: JSON.stringify(patch) });
      const next = await api<Me>("/api/user/me");
      setMe(next);
      setMsg(t("settings.saved", (next.lang as Lang) || "id"));
    } catch (e: any) {
      setMsg(e.message);
    }
  }

  async function logout() {
    try {
      await api("/api/user/logout", { method: "POST" });
    } catch {
      /* ignore */
    }
    setToken(null);
    router.replace("/");
  }

  if (!me) {
    return (
      <AppShell lang="id">
        <PageLoader label={t("loading", "id")} cards={2} />
      </AppShell>
    );
  }

  return (
    <AppShell lang={lang}>
      <h2 className="mb-4 text-xl font-semibold">{t("settings.title", lang)}</h2>

      <section className="mb-6 rounded-xl border border-border bg-card p-4">
        <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {t("settings.lang", lang)}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => save({ lang: "id" })}
            className={`min-h-[44px] flex-1 rounded-lg border px-3 text-sm font-medium ${
              lang === "id" ? "border-primary bg-primary/15 text-primary" : "border-border"
            }`}
          >
            ID
          </button>
          <button
            type="button"
            onClick={() => save({ lang: "en" })}
            className={`min-h-[44px] flex-1 rounded-lg border px-3 text-sm font-medium ${
              lang === "en" ? "border-primary bg-primary/15 text-primary" : "border-border"
            }`}
          >
            EN
          </button>
        </div>
      </section>

      <section className="mb-6 rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-medium">{t("settings.gallery", lang)}</div>
            <p className="mt-1 text-xs text-muted-foreground">{t("settings.galleryHint", lang)}</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={me.gallery_public}
            onClick={() => save({ gallery_public: !me.gallery_public })}
            className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${
              me.gallery_public ? "bg-primary" : "bg-muted"
            }`}
          >
            <span
              className={`absolute top-0.5 h-6 w-6 rounded-full bg-white transition-transform ${
                me.gallery_public ? "left-5" : "left-0.5"
              }`}
            />
          </button>
        </div>
      </section>

      {msg && <p className="mb-4 text-center text-xs text-muted-foreground">{msg}</p>}

      <button
        type="button"
        onClick={logout}
        className="flex min-h-[48px] w-full items-center justify-center rounded-xl border border-destructive/40 text-sm font-semibold text-destructive"
      >
        {t("settings.logout", lang)}
      </button>
    </AppShell>
  );
}
