"use client";

import { useEffect, useRef } from "react";

declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramUser) => void;
  }
}

export type TelegramUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
};

type Props = {
  botUsername: string;
  onAuth: (user: TelegramUser) => void;
  lang?: "id" | "en";
};

/** Renders official Telegram Login Widget into a host div. */
export function TelegramLoginButton({ botUsername, onAuth, lang = "id" }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    window.onTelegramAuth = (user) => onAuth(user);

    const host = hostRef.current;
    if (!host) return;
    host.innerHTML = "";

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "12");
    script.setAttribute("data-request-access", "write");
    script.setAttribute("data-userpic", "false");
    script.setAttribute("data-lang", lang === "id" ? "id" : "en");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    host.appendChild(script);

    return () => {
      delete window.onTelegramAuth;
      if (host) host.innerHTML = "";
    };
  }, [botUsername, onAuth, lang]);

  return <div ref={hostRef} className="flex min-h-[44px] justify-center" />;
}
