"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Loader2 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { api, getToken, type Me } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

type Job = {
  job_id: string;
  status: string;
  position?: number;
  eta_sec?: number;
  error?: string | null;
  image_data_url?: string;
  has_image?: boolean;
};

export default function GeneratePage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("id");
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState("1024x1024");
  const [styleCode, setStyleCode] = useState("");
  const [styles, setStyles] = useState<{ code: string; name: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

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
      } catch {
        router.replace("/");
      }
    })();
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [router]);

  async function poll(jobId: string) {
    try {
      const j = await api<Job>(`/api/user/generate/${jobId}`);
      setJob(j);
      if (j.status === "done" || j.status === "failed") {
        setBusy(false);
        if (pollRef.current) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
        if (j.status === "done" && j.image_data_url) {
          try {
            await api(`/api/user/generate/${jobId}/image`, { method: "DELETE" });
          } catch {
            /* ignore */
          }
        }
      }
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  }

  async function submit() {
    setErr(null);
    setJob(null);
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      const res = await api<{ job_id: string; status: string; position: number; eta_sec: number }>(
        "/api/user/generate",
        {
          method: "POST",
          body: JSON.stringify({
            prompt: prompt.trim(),
            size,
            style_code: styleCode || null,
          }),
        }
      );
      setJob({
        job_id: res.job_id,
        status: res.status,
        position: res.position,
        eta_sec: res.eta_sec,
      });
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = window.setInterval(() => poll(res.job_id), 2000);
      await poll(res.job_id);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
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
        disabled={busy}
        className="w-full resize-none rounded-xl border border-border bg-card p-3 text-sm outline-none ring-ring focus:ring-2 disabled:opacity-60"
      />

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-[11px] uppercase text-muted-foreground">Size</label>
          <select
            value={size}
            onChange={(e) => setSize(e.target.value)}
            disabled={busy}
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
            disabled={busy}
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
        disabled={busy || !prompt.trim()}
        className="mt-4 flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
      >
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
        {t("gen.submit", lang)}
      </button>

      {err && (
        <div className="mt-4 flex gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span className="break-all">{err}</span>
        </div>
      )}

      {job && (
        <div className="mt-4 rounded-xl border border-border bg-card p-4 text-sm">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            {job.status}
            {job.status === "queued" || job.status === "running"
              ? ` · pos ${job.position ?? "—"} · ~${job.eta_sec ?? "?"}s`
              : ""}
          </div>
          {job.error && <p className="mt-2 text-destructive">{job.error}</p>}
          {job.image_data_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={job.image_data_url}
              alt="result"
              className="mt-3 w-full rounded-lg border border-border"
            />
          )}
        </div>
      )}
    </AppShell>
  );
}
