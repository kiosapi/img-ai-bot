"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ImageIcon } from "lucide-react";
import { AppShell } from "@/components/shell";
import { ListSkeleton } from "@/components/page-loader";
import { api, getToken, type Me } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

type Item = {
  id: number;
  prompt: string;
  kind: string | null;
  success: boolean;
  size: string | null;
  created_at: string | null;
  has_result: boolean;
};

export default function HistoryPage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("id");
  const [items, setItems] = useState<Item[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    (async () => {
      try {
        const me = await api<Me>("/api/user/me");
        setLang((me.lang as Lang) || "id");
        const h = await api<{ items: Item[] }>("/api/user/history?limit=30");
        setItems(h.items);
      } catch (e: any) {
        setErr(e.message);
      }
    })();
  }, [router]);

  return (
    <AppShell lang={lang}>
      <h2 className="mb-4 text-xl font-semibold">{t("history.title", lang)}</h2>
      {err && <p className="text-sm text-destructive">{err}</p>}
      {!items && !err && <ListSkeleton rows={5} />}
      {items && items.length === 0 && (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border py-12 text-muted-foreground">
          <ImageIcon className="h-8 w-8" />
          <p className="text-sm">{t("history.empty", lang)}</p>
        </div>
      )}
      <ul className="flex flex-col gap-2">
        {items?.map((it) => (
          <li key={it.id} className="rounded-xl border border-border bg-card p-3">
            <div className="mb-1 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
              <span className="uppercase">{it.kind || "gen"}</span>
              <span>{it.created_at ? new Date(it.created_at).toLocaleString() : ""}</span>
            </div>
            <p className="line-clamp-3 text-sm">{it.prompt || "—"}</p>
            <div className="mt-2 flex gap-2 text-[11px]">
              <span className={it.success ? "text-success" : "text-destructive"}>
                {it.success ? "OK" : "FAIL"}
              </span>
              {it.size && <span className="text-muted-foreground">{it.size}</span>}
            </div>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}
