"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { CheckCircle2, XCircle, X, Sparkles } from "lucide-react";
import { useGenJob, patchJobNotified } from "@/lib/gen-job";
import { t, type Lang } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function formatEta(sec: number, lang: Lang) {
  const s = Math.max(0, Math.round(sec));
  if (s < 60) return lang === "id" ? `~${s} dtk` : `~${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return lang === "id" ? `~${m}m ${r}d` : `~${m}m ${r}s`;
}

export function GenProgressBar({ lang }: { lang: Lang }) {
  const { job, dismiss, clearResult } = useGenJob();
  const toastShown = useRef(false);

  useEffect(() => {
    if (!job) {
      toastShown.current = false;
      return;
    }
    if (job.status === "done" && !job.notified && !toastShown.current) {
      toastShown.current = true;
      patchJobNotified();
      // auto-dismiss banner after 45s on success if user stays
      const tmr = window.setTimeout(() => {
        /* keep result visible until clear */
      }, 45000);
      return () => window.clearTimeout(tmr);
    }
  }, [job]);

  if (!job || job.dismissed) return null;

  const active = job.status === "queued" || job.status === "running";
  const done = job.status === "done";
  const failed = job.status === "failed";

  // remaining ETA estimate
  let remain = job.etaSec || 40;
  if (job.status === "running" && job.startedAt) {
    const elapsed = (Date.now() - job.startedAt) / 1000;
    remain = Math.max(3, (job.etaSec || 45) - elapsed);
  } else if (job.status === "queued") {
    remain = Math.max(10, (job.position || 1) * 40);
  }

  return (
    <div
      className={cn(
        "fixed left-0 right-0 z-40 px-3",
        "bottom-[4.5rem] sm:bottom-[4.75rem]"
      )}
    >
      <div
        className={cn(
          "mx-auto max-w-lg overflow-hidden rounded-2xl border shadow-xl sm:max-w-2xl",
          done && "border-success/40 bg-card",
          failed && "border-destructive/40 bg-card",
          active && "border-primary/30 bg-card/95 backdrop-blur-md"
        )}
      >
        <div className="flex items-start gap-3 p-3">
          <div
            className={cn(
              "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
              done && "bg-success/15 text-success",
              failed && "bg-destructive/15 text-destructive",
              active && "bg-primary/15 text-primary"
            )}
          >
            {done ? (
              <CheckCircle2 className="h-5 w-5" />
            ) : failed ? (
              <XCircle className="h-5 w-5" />
            ) : (
              <Sparkles className="h-5 w-5 animate-pulse" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-sm font-semibold">
                {done
                  ? t("gen.toastDone", lang)
                  : failed
                    ? t("gen.toastFail", lang)
                    : job.status === "queued"
                      ? t("gen.queue", lang)
                      : t("gen.running", lang)}
              </p>
              <button
                type="button"
                onClick={() => (active ? dismiss() : clearResult())}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
              {job.prompt || "—"}
            </p>
            {active && (
              <>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                    style={{ width: `${Math.round(job.progress)}%` }}
                  />
                </div>
                <div className="mt-1.5 flex justify-between text-[11px] text-muted-foreground">
                  <span>
                    {Math.round(job.progress)}%
                    {job.status === "queued" && job.position
                      ? ` · ${t("gen.pos", lang)} ${job.position}`
                      : ""}
                  </span>
                  <span>
                    {t("gen.eta", lang)} {formatEta(remain, lang)}
                  </span>
                </div>
              </>
            )}
            {failed && job.error && (
              <p className="mt-1 text-xs text-destructive break-all">{job.error}</p>
            )}
            {done && (
              <Link
                href="/app/generate/"
                className="mt-2 inline-flex text-xs font-medium text-primary hover:underline"
              >
                {t("gen.viewResult", lang)}
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
