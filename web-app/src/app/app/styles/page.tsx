"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Palette } from "lucide-react";
import { AppShell } from "@/components/shell";
import { api, getToken, type Me } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

type Style = {
  code: string;
  name: string;
  prompt_prefix: string;
  thumbnail_url: string | null;
  category: string;
};

export default function StylesPage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("id");
  const [styles, setStyles] = useState<Style[] | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    (async () => {
      try {
        const me = await api<Me>("/api/user/me");
        setLang((me.lang as Lang) || "id");
        const s = await api<{ styles: Style[] }>("/api/user/styles");
        setStyles(s.styles);
      } catch {
        router.replace("/");
      }
    })();
  }, [router]);

  return (
    <AppShell lang={lang}>
      <h2 className="mb-4 text-xl font-semibold">{t("styles.title", lang)}</h2>
      {!styles && <p className="text-sm text-muted-foreground">{t("loading", lang)}</p>}
      {styles && styles.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <Palette className="h-8 w-8" />
          <p className="text-sm">{t("styles.empty", lang)}</p>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {styles?.map((s) => (
          <div key={s.code} className="rounded-xl border border-border bg-card p-3">
            <div className="mb-2 flex h-16 items-center justify-center rounded-lg bg-muted">
              {s.thumbnail_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={s.thumbnail_url} alt="" className="h-full w-full rounded-lg object-cover" />
              ) : (
                <Palette className="h-6 w-6 text-muted-foreground" />
              )}
            </div>
            <div className="truncate text-sm font-medium">{s.name}</div>
            <div className="truncate text-[11px] uppercase text-muted-foreground">{s.category}</div>
          </div>
        ))}
      </div>
    </AppShell>
  );
}
