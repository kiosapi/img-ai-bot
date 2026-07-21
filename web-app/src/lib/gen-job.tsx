"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api, getToken } from "@/lib/utils";

const STORAGE_KEY = "imgaai_active_gen_job";

export type GenJobSnapshot = {
  jobId: string;
  status: "queued" | "running" | "done" | "failed" | string;
  position: number;
  etaSec: number;
  progress: number;
  error: string | null;
  imageDataUrl: string | null;
  prompt: string;
  startedAt: number | null;
  createdAt: number;
  dismissed: boolean;
  notified: boolean;
};

type StartArgs = {
  prompt: string;
  size: string;
  style_code?: string | null;
};

type Ctx = {
  job: GenJobSnapshot | null;
  busy: boolean;
  start: (args: StartArgs) => Promise<void>;
  dismiss: () => void;
  clearResult: () => void;
};

const GenJobCtx = createContext<Ctx | null>(null);

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

function calcProgress(
  status: string,
  etaSec: number,
  startedAt: number | null,
  createdAt: number,
  position: number
): number {
  if (status === "done") return 100;
  if (status === "failed") return 100;
  const now = Date.now();
  if (status === "queued") {
    // queue: 2–18% based on position
    const pos = Math.max(1, position || 1);
    return clamp(4 + Math.min(14, 20 / pos) + ((now - createdAt) / 1000) * 0.15, 2, 22);
  }
  // running: time-based toward 92%
  const start = startedAt || createdAt;
  const eta = Math.max(20, etaSec || 45);
  const elapsed = (now - start) / 1000;
  const raw = 22 + (elapsed / eta) * 70;
  return clamp(raw, 22, 92);
}

function loadStored(): GenJobSnapshot | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const j = JSON.parse(raw) as GenJobSnapshot;
    if (!j?.jobId) return null;
    // drop ancient done/failed
    if (
      (j.status === "done" || j.status === "failed") &&
      Date.now() - (j.createdAt || 0) > 1000 * 60 * 30
    ) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return j;
  } catch {
    return null;
  }
}

function saveStored(job: GenJobSnapshot | null) {
  if (typeof window === "undefined") return;
  if (!job) localStorage.removeItem(STORAGE_KEY);
  else localStorage.setItem(STORAGE_KEY, JSON.stringify(job));
}

export function GenJobProvider({ children }: { children: React.ReactNode }) {
  const [job, setJob] = useState<GenJobSnapshot | null>(null);
  const pollRef = useRef<number | null>(null);
  const tickRef = useRef<number | null>(null);
  const hydrated = useRef(false);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyPoll = useCallback(async (jobId: string) => {
    if (!getToken()) return;
    try {
      const j = await api<{
        job_id: string;
        status: string;
        position?: number;
        eta_sec?: number;
        error?: string | null;
        image_data_url?: string;
        has_image?: boolean;
        prompt?: string;
      }>(`/api/user/generate/${jobId}`);

      setJob((prev) => {
        if (!prev || prev.jobId !== jobId) return prev;
        const status = j.status;
        const position = j.position ?? prev.position;
        const etaSec = j.eta_sec ?? prev.etaSec;
        const startedAt =
          status === "running" && !prev.startedAt ? Date.now() : prev.startedAt;
        const next: GenJobSnapshot = {
          ...prev,
          status,
          position,
          etaSec,
          error: j.error || null,
          prompt: j.prompt || prev.prompt,
          startedAt,
          imageDataUrl: j.image_data_url || prev.imageDataUrl,
          progress: calcProgress(status, etaSec, startedAt, prev.createdAt, position),
        };
        if (status === "done" && j.image_data_url) {
          next.progress = 100;
          // clear b64 on server after client has it
          api(`/api/user/generate/${jobId}/image`, { method: "DELETE" }).catch(() => {});
        }
        if (status === "failed") next.progress = 100;
        saveStored(next);
        return next;
      });
    } catch {
      /* keep previous */
    }
  }, []);

  const ensurePolling = useCallback(
    (jobId: string, status: string) => {
      stopPoll();
      if (status === "done" || status === "failed") return;
      pollRef.current = window.setInterval(() => applyPoll(jobId), 2000);
      applyPoll(jobId);
    },
    [applyPoll, stopPoll]
  );

  // hydrate + smooth progress tick
  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    const stored = loadStored();
    if (stored) {
      setJob(stored);
      if (stored.status === "queued" || stored.status === "running") {
        ensurePolling(stored.jobId, stored.status);
      }
    }
  }, [ensurePolling]);

  useEffect(() => {
    if (tickRef.current) window.clearInterval(tickRef.current);
    tickRef.current = window.setInterval(() => {
      setJob((prev) => {
        if (!prev) return prev;
        if (prev.status !== "queued" && prev.status !== "running") return prev;
        const progress = calcProgress(
          prev.status,
          prev.etaSec,
          prev.startedAt,
          prev.createdAt,
          prev.position
        );
        if (progress === prev.progress) return prev;
        const next = { ...prev, progress };
        saveStored(next);
        return next;
      });
    }, 500);
    return () => {
      if (tickRef.current) window.clearInterval(tickRef.current);
    };
  }, []);

  // stop poll when terminal
  useEffect(() => {
    if (!job) return;
    if (job.status === "done" || job.status === "failed") stopPoll();
  }, [job, stopPoll]);

  const start = useCallback(
    async (args: StartArgs) => {
      if (!getToken()) throw new Error("unauthorized");
      const res = await api<{
        job_id: string;
        status: string;
        position: number;
        eta_sec: number;
      }>("/api/user/generate", {
        method: "POST",
        body: JSON.stringify({
          prompt: args.prompt.trim(),
          size: args.size,
          style_code: args.style_code || null,
        }),
      });
      const snap: GenJobSnapshot = {
        jobId: res.job_id,
        status: res.status,
        position: res.position || 1,
        etaSec: res.eta_sec || 45,
        progress: 5,
        error: null,
        imageDataUrl: null,
        prompt: args.prompt.trim(),
        startedAt: res.status === "running" ? Date.now() : null,
        createdAt: Date.now(),
        dismissed: false,
        notified: false,
      };
      setJob(snap);
      saveStored(snap);
      ensurePolling(res.job_id, res.status);
    },
    [ensurePolling]
  );

  const dismiss = useCallback(() => {
    setJob((prev) => {
      if (!prev) return null;
      if (prev.status === "queued" || prev.status === "running") {
        const next = { ...prev, dismissed: true };
        saveStored(next);
        return next;
      }
      saveStored(null);
      return null;
    });
  }, []);

  const clearResult = useCallback(() => {
    stopPoll();
    setJob(null);
    saveStored(null);
  }, [stopPoll]);

  const busy = !!(job && (job.status === "queued" || job.status === "running"));

  const value = useMemo(
    () => ({ job, busy, start, dismiss, clearResult }),
    [job, busy, start, dismiss, clearResult]
  );

  return <GenJobCtx.Provider value={value}>{children}</GenJobCtx.Provider>;
}

export function useGenJob() {
  const ctx = useContext(GenJobCtx);
  if (!ctx) throw new Error("useGenJob outside provider");
  return ctx;
}

/** Optional: mark success toast already shown */
export function useMarkJobNotified() {
  const { job } = useGenJob();
  const setNotified = useCallback(() => {
    if (!job) return;
    const next = { ...job, notified: true };
    saveStored(next);
  }, [job]);
  return setNotified;
}

export function patchJobNotified() {
  const j = loadStored();
  if (!j) return;
  j.notified = true;
  saveStored(j);
}
