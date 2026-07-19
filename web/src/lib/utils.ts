import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export async function api<T = any>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts?.headers || {}) },
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** Upload multipart/form-data (e.g. images). Do NOT set Content-Type manually —
 * the browser sets it (with the multipart boundary) from the FormData body. */
export async function apiUpload<T = any>(path: string, form: FormData): Promise<T> {
  const res = await fetch(path, { method: "POST", body: form, credentials: "include" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
