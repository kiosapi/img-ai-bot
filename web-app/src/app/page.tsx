"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, AlertCircle } from "lucide-react";
import { TelegramLoginButton, type TelegramUser } from "@/components/telegram-login";
import { api, getToken, setToken } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

const BOT = process.env.NEXT_PUBLIC_BOT_USERNAME || "imgaai_bot";

export default function LoginPage() {
  const router = useRouter();
  const [lang] = useState<Lang>("id");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) router.replace("/app/");
  }, [router]);

  const onAuth = useCallback(
    async (user: TelegramUser) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api<{ ok: boolean; token: string }>("/api/user/auth/telegram", {
          method: "POST",
          body: JSON.stringify(user),
        });
        setToken(res.token);
        router.replace("/app/");
      } catch (e: any) {
        setError(e?.message || t("err.generic", lang));
      } finally {
        setLoading(false);
      }
    },
    [router, lang]
  );

  return (
    <div className="bg-grid flex min-h-screen items-center justify-center p-5">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-xl">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
          <Sparkles className="h-7 w-7" />
        </div>
        <h1 className="text-center text-2xl font-bold tracking-tight">{t("app.name", lang)}</h1>
        <p className="mt-1 text-center text-sm text-muted-foreground">{t("login.title", lang)}</p>
        <p className="mb-6 mt-2 text-center text-xs text-muted-foreground">{t("login.sub", lang)}</p>

        {loading ? (
          <p className="text-center text-sm text-muted-foreground">{t("loading", lang)}</p>
        ) : (
          <TelegramLoginButton botUsername={BOT} onAuth={onAuth} lang={lang} />
        )}

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="break-all">{error}</span>
          </div>
        )}

        <p className="mt-6 text-center text-[11px] text-muted-foreground">{t("login.needDomain", lang)}</p>
        <p className="mt-1 text-center text-[11px] text-muted-foreground">{t("login.devHint", lang)}</p>
      </div>
    </div>
  );
}
