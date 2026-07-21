import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

const TOKEN_KEY = "imgaai_user_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function api<T = any>(path: string, opts?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts?.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(typeof err.detail === "string" ? err.detail : `HTTP ${res.status}`);
  }
  return res.json();
}

export type Me = {
  user_id: number;
  username: string | null;
  first_name: string | null;
  balance: number;
  lang: string;
  gallery_public: boolean;
  pref_size: string | null;
  premium: null | {
    plan_name: string | null;
    premium_until: string;
    daily_limit: number | null;
  };
  quota: { used: number; limit: number };
  checkin: { streak: number; last_checkin: string | null; total_checkin: number };
};
