"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, AlertCircle, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import { api, getToken, setToken } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

const BOT = process.env.NEXT_PUBLIC_BOT_USERNAME || "imgaai_bot";
const POLL_MS = 2000;
const MAX_POLLS = 150; // ~5 min

type LoginCodeRes = {
  ok: boolean;
  code: string;
  deep_link: string;
  expires_in: number;
};

type PollRes = {
  status: "pending" | "claimed" | "expired" | string;
  token?: string;
  user_id?: number;
};

export default function LoginPage() {
  const router = useRouter();
  const [lang] = useState<Lang>("id");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [deepLink, setDeepLink] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const polls = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => {
    if (getToken()) router.replace("/app/");
    return () => stopPoll();
  }, [router, stopPoll]);

  const startPoll = useCallback(
    (loginCode: string) => {
      stopPoll();
      polls.current = 0;
      setWaiting(true);
      timer.current = setInterval(async () => {
        polls.current += 1;
        if (polls.current > MAX_POLLS) {
          stopPoll();
          setWaiting(false);
          setError(t("login.expired", lang));
          return;
        }
        try {
          const res = await api<PollRes>(`/api/user/auth/login-code/${loginCode}`);
          if (res.status === "claimed" && res.token) {
            stopPoll();
            setToken(res.token);
            router.replace("/app/");
            return;
          }
          if (res.status === "expired") {
            stopPoll();
            setWaiting(false);
            setError(t("login.expired", lang));
          }
        } catch {
          // keep polling on transient errors
        }
      }, POLL_MS);
    },
    [lang, router, stopPoll]
  );

  const beginLogin = useCallback(async () => {
    setLoading(true);
    setError(null);
    stopPoll();
    try {
      const res = await api<LoginCodeRes>("/api/user/auth/login-code", { method: "POST" });
      setCode(res.code);
      setDeepLink(res.deep_link);
      // open Telegram
      window.open(res.deep_link, "_blank", "noopener,noreferrer");
      startPoll(res.code);
    } catch (e: any) {
      setError(e?.message || t("err.generic", lang));
      setWaiting(false);
    } finally {
      setLoading(false);
    }
  }, [lang, startPoll, stopPoll]);

  return (
    <div className="bg-grid flex min-h-screen items-center justify-center p-5">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-xl">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
          <Sparkles className="h-7 w-7" />
        </div>
        <h1 className="text-center text-2xl font-bold tracking-tight">{t("app.name", lang)}</h1>
        <p className="mt-1 text-center text-sm text-muted-foreground">{t("login.title", lang)}</p>
        <p className="mb-6 mt-2 text-center text-xs text-muted-foreground">{t("login.sub", lang)}</p>

        {!waiting ? (
          <button
            type="button"
            onClick={beginLogin}
            disabled={loading}
            className="flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {t("loading", lang)}
              </>
            ) : (
              <>
                <ExternalLink className="h-4 w-4" />
                {t("login.cta", lang)}
              </>
            )}
          </button>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="rounded-xl border border-border bg-muted/40 p-4 text-center">
              <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-primary" />
              <p className="text-sm font-medium">{t("login.waiting", lang)}</p>
              <p className="mt-1 text-xs text-muted-foreground">{t("login.waitingHint", lang)}</p>
            </div>
            {deepLink && (
              <a
                href={deepLink}
                target="_blank"
                rel="noopener noreferrer"
                className="flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-border px-3 py-2 text-sm font-medium hover:bg-accent"
              >
                <ExternalLink className="h-4 w-4" />
                {t("login.openAgain", lang)}
              </a>
            )}
            <button
              type="button"
              onClick={() => {
                stopPoll();
                setWaiting(false);
                setCode(null);
                setDeepLink(null);
                setError(null);
              }}
              className="flex min-h-[44px] items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm text-muted-foreground hover:bg-accent"
            >
              <RefreshCw className="h-4 w-4" />
              {t("login.cancelWait", lang)}
            </button>
          </div>
        )}

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span className="break-all">{error}</span>
          </div>
        )}

        <p className="mt-6 text-center text-[11px] text-muted-foreground">{t("login.flowHint", lang)}</p>
        <p className="mt-1 text-center text-[11px] text-muted-foreground">@{BOT}</p>
      </div>
    </div>
  );
}
