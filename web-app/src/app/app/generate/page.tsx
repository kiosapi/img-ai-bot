"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Loader2, CheckCircle2 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { PageLoader } from "@/components/page-loader";
import { api, getToken, type Me } from "@/lib/utils";
import { useGenJob } from "@/lib/gen-job";
import { t, type Lang } from "@/lib/i18n";

export default function GeneratePage() {
  const router = useRouter();
  const { job, busy, start, clearResult } = useGenJob();
  const [lang, setLang] = useState<Lang>("id");
  const [ready, setReady] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState("1024x1024");
  const [styleCode, setStyleCode] = useState("");
  const [styles, setStyles] = useState<{ code: string; name: string }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    (async () => {
      try {
        const me = await api<Me>("/api/user/me");
        setLang((me.lang as Lang) || "id");
        const s = await api<{ styles: { code: string; name: string }[] }>("/api/user/styles");
        setStyles(s.styles || []);
        setReady(true);
      } catch {
        router.replace("/");
      }
    })();
  }, [router]);

  async function submit() {
    setErr(null);
    if (!prompt.trim() || busy || submitting) return;
    setSubmitting(true);
    try {
      await start({
        prompt: prompt.trim(),
        size,
        style_code: styleCode || null,
      });
    } catch (e: any) {
      setErr(e?.message || t("err.generic", lang));
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready) {
    return (
      <AppShell lang={lang}>
        <PageLoader label={t("loading", lang)} cards={2} />
      </AppShell>
    );
  }

  return (
    <AppShell lang={lang}>
      <h2 className="mb-4 text-xl font-semibold">{t("gen.title", lang)}</h2>
      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {t("gen.prompt", lang)}
      </label>
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        rows={5}
        placeholder={t("gen.placeholder", lang)}
        disabled={busy || submitting}
        className="w-full resize-none rounded-xl border border-border bg-card p-3 text-sm outline-none ring-ring focus:ring-2 disabled:opacity-60"
      />

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[11px] uppercase text-muted-foreground">Size</label>
          <select
            value={size}
            onChange={(e) => setSize(e.target.value)}
            disabled={busy || submitting}
            className="min-h-[44px] w-full rounded-xl border border-border bg-card px-3 text-sm"
          >
            <option value="1024x1024">1:1</option>
            <option value="1024x1792">9:16</option>
            <option value="1792x1024">16:9</option>
            <option value="1024x1536">2:3</option>
            <option value="1536x1024">3:2</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-[11px] uppercase text-muted-foreground">Style</label>
          <select
            value={styleCode}
            onChange={(e) => setStyleCode(e.target.value)}
            disabled={busy || submitting}
            className="min-h-[44px] w-full rounded-xl border border-border bg-card px-3 text-sm"
          >
            <option value="">—</option>
            {styles.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button
        type="button"
        onClick={submit}
        disabled={busy || submitting || !prompt.trim()}
        className="mt-4 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
      >
        {(busy || submitting) && <Loader2 className="h-4 w-4 animate-spin" />}
        {busy ? t("gen.running", lang) : t("gen.submit", lang)}
      </button>

      {err && (
        <div className="mt-4 flex gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span className="break-all">{err}</span>
        </div>
      )}

      {job && (job.status === "queued" || job.status === "running") && (
        <div className="mt-4 rounded-xl border border-primary/25 bg-card p-4">
          <div className="mb-2 flex items-center justify-between text-sm font-medium">
            <span>
              {job.status === "queued" ? t("gen.queue", lang) : t("gen.running", lang)}
            </span>
            <span className="text-xs text-muted-foreground">{Math.round(job.progress)}%</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500"
              style={{ width: `${Math.round(job.progress)}%` }}
            />
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {job.status === "queued" && job.position
              ? `${t("gen.pos", lang)} ${job.position} · `
              : ""}
            {t("gen.eta", lang)} ~{Math.max(3, Math.round(job.etaSec || 40))}s
            {" · "}
            {t("gen.persistHint", lang)}
          </p>
        </div>
      )}

      {job?.status === "done" && (
        <div className="mt-4 rounded-xl border border-success/40 bg-card p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-success">
            <CheckCircle2 className="h-4 w-4" />
            {t("gen.toastDone", lang)}
          </div>
          {job.imageDataUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={job.imageDataUrl}
              alt="result"
              className="w-full rounded-lg border border-border"
            />
          ) : (
            <p className="text-xs text-muted-foreground">{t("gen.resultReady", lang)}</p>
          )}
          <button
            type="button"
            onClick={clearResult}
            className="mt-3 min-h-[40px] w-full rounded-xl border border-border text-sm font-medium hover:bg-muted"
          >
            {t("gen.clear", lang)}
          </button>
        </div>
      )}

      {job?.status === "failed" && (
        <div className="mt-4 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {t("gen.toastFail", lang)}
          {job.error ? `: ${job.error}` : ""}
          <button
            type="button"
            onClick={clearResult}
            className="mt-3 block min-h-[40px] w-full rounded-xl border border-destructive/30 text-sm font-medium"
          >
            {t("gen.clear", lang)}
          </button>
        </div>
      )}
    </AppShell>
  );
}
