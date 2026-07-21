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
// images stay in memory only — localStorage quota dies on 2–3MB data URLs
const IMAGE_MEM = new Map<string, string>();

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
  if (status === "done" || status === "failed") return 100;
  const now = Date.now();
  if (status === "queued") {
    const pos = Math.max(1, position || 1);
    return clamp(3 + Math.min(12, 18 / pos) + ((now - createdAt) / 1000) * 0.05, 2, 18);
  }
  const start = startedAt || createdAt;
  const eta = Math.max(60, etaSec || 150);
  const elapsed = (now - start) / 1000;
  // asymptotic toward 94% so long jobs never look "stuck at 100% while Processing"
  const raw = 18 + (1 - Math.exp(-elapsed / Math.max(40, eta * 0.55))) * 76;
  return clamp(raw, 18, 94);
}

type StoredMeta = Omit<GenJobSnapshot, "imageDataUrl">;

function loadStored(): GenJobSnapshot | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const j = JSON.parse(raw) as StoredMeta;
    if (!j?.jobId) return null;
    if (
      (j.status === "done" || j.status === "failed") &&
      Date.now() - (j.createdAt || 0) > 1000 * 60 * 30
    ) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return {
      ...j,
      imageDataUrl: IMAGE_MEM.get(j.jobId) || null,
    };
  } catch {
    return null;
  }
}

function saveStored(job: GenJobSnapshot | null) {
  if (typeof window === "undefined") return;
  if (!job) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }
  if (job.imageDataUrl) IMAGE_MEM.set(job.jobId, job.imageDataUrl);
  // never persist imageDataUrl — quota / stringify hang
  const { imageDataUrl: _drop, ...meta } = job;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(meta));
  } catch {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ ...meta, imageDataUrl: undefined, prompt: (meta.prompt || "").slice(0, 120) })
      );
    } catch {
      /* ignore */
    }
  }
}

export function GenJobProvider({ children }: { children: React.ReactNode }) {
  const [job, setJob] = useState<GenJobSnapshot | null>(null);
  const pollRef = useRef<number | null>(null);
  const tickRef = useRef<number | null>(null);
  const hydrated = useRef(false);
  const fetchingImg = useRef<string | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchImage = useCallback(async (jobId: string) => {
    if (fetchingImg.current === jobId) return;
    if (IMAGE_MEM.has(jobId)) {
      setJob((prev) => {
        if (!prev || prev.jobId !== jobId) return prev;
        if (prev.imageDataUrl) return prev;
        const next = { ...prev, imageDataUrl: IMAGE_MEM.get(jobId) || null, progress: 100 };
        saveStored(next);
        return next;
      });
      return;
    }
    fetchingImg.current = jobId;
    try {
      const img = await api<{ image_data_url?: string; has_image?: boolean }>(
        `/api/user/generate/${jobId}/image`
      );
      const url = img.image_data_url || null;
      if (url) IMAGE_MEM.set(jobId, url);
      setJob((prev) => {
        if (!prev || prev.jobId !== jobId) return prev;
        const next: GenJobSnapshot = {
          ...prev,
          status: "done",
          progress: 100,
          imageDataUrl: url || prev.imageDataUrl,
        };
        saveStored(next);
        return next;
      });
      // free DB after client has bytes
      api(`/api/user/generate/${jobId}/image`, { method: "DELETE" }).catch(() => {});
    } catch {
      // status may still be done without image — surface done anyway
      setJob((prev) => {
        if (!prev || prev.jobId !== jobId) return prev;
        if (prev.status === "done") return prev;
        const next = { ...prev, status: "done", progress: 100 };
        saveStored(next);
        return next;
      });
    } finally {
      if (fetchingImg.current === jobId) fetchingImg.current = null;
    }
  }, []);

  const applyPoll = useCallback(
    async (jobId: string) => {
      if (!getToken()) return;
      try {
        const j = await api<{
          job_id: string;
          status: string;
          position?: number;
          eta_sec?: number;
          error?: string | null;
          has_image?: boolean;
          prompt?: string;
          started_at?: string | null;
        }>(`/api/user/generate/${jobId}`);

        let shouldFetchImg = false;
        setJob((prev) => {
          if (!prev || prev.jobId !== jobId) return prev;
          const status = j.status;
          const position = j.position ?? prev.position;
          const etaSec = j.eta_sec ?? prev.etaSec;
          let startedAt = prev.startedAt;
          if (status === "running" && !startedAt) {
            if (j.started_at) {
              const t = Date.parse(j.started_at);
              startedAt = Number.isFinite(t) ? t : Date.now();
            } else {
              startedAt = Date.now();
            }
          }
          const next: GenJobSnapshot = {
            ...prev,
            status,
            position,
            etaSec,
            error: j.error || null,
            prompt: j.prompt || prev.prompt,
            startedAt,
            progress: calcProgress(status, etaSec, startedAt, prev.createdAt, position),
            imageDataUrl: prev.imageDataUrl || IMAGE_MEM.get(jobId) || null,
          };
          if (status === "done") {
            next.progress = 100;
            if (!next.imageDataUrl && j.has_image) shouldFetchImg = true;
          }
          if (status === "failed") next.progress = 100;
          saveStored(next);
          return next;
        });
        if (shouldFetchImg || (j.status === "done" && j.has_image && !IMAGE_MEM.has(jobId))) {
          void fetchImage(jobId);
        }
      } catch {
        /* keep previous — do not swallow forever: next tick retries */
      }
    },
    [fetchImage]
  );

  const ensurePolling = useCallback(
    (jobId: string, status: string) => {
      stopPoll();
      if (status === "done" || status === "failed") {
        if (status === "done") void fetchImage(jobId);
        return;
      }
      pollRef.current = window.setInterval(() => applyPoll(jobId), 1500);
      applyPoll(jobId);
    },
    [applyPoll, fetchImage, stopPoll]
  );

  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    const stored = loadStored();
    if (stored) {
      setJob(stored);
      if (stored.status === "queued" || stored.status === "running") {
        ensurePolling(stored.jobId, stored.status);
      } else if (stored.status === "done" && !stored.imageDataUrl) {
        void fetchImage(stored.jobId);
      }
    }
  }, [ensurePolling, fetchImage]);

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
    }, 400);
    return () => {
      if (tickRef.current) window.clearInterval(tickRef.current);
    };
  }, []);

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
        etaSec: res.eta_sec || 150,
        progress: 4,
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
      IMAGE_MEM.delete(prev.jobId);
      saveStored(null);
      return null;
    });
  }, []);

  const clearResult = useCallback(() => {
    stopPoll();
    setJob((prev) => {
      if (prev) IMAGE_MEM.delete(prev.jobId);
      return null;
    });
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

export function patchJobNotified() {
  const j = loadStored();
  if (!j) return;
  j.notified = true;
  saveStored(j);
}
