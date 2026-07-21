"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Coins, Gauge, Flame, Crown, Sparkles } from "lucide-react";
import { AppShell } from "@/components/shell";
import { PageLoader } from "@/components/page-loader";
import { api, getToken, type Me } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

export default function HomePage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const lang: Lang = (me?.lang as Lang) || "id";

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    api<Me>("/api/user/me")
      .then(setMe)
      .catch((e) => setErr(e.message));
  }, [router]);

  if (err) {
    return (
      <div className="flex min-h-screen items-center justify-center p-5 text-sm text-destructive">
        {err}
      </div>
    );
  }

  if (!me) {
    return (
      <AppShell lang="id">
        <PageLoader label={t("loading", "id")} cards={4} />
      </AppShell>
    );
  }

  const name = me.first_name || me.username || String(me.user_id);

  return (
    <AppShell lang={lang}>
      <h2 className="mb-4 text-xl font-semibold tracking-tight">
        {t("home.welcome", lang)}, {name}
      </h2>

      <div className="grid grid-cols-2 gap-3">
        <Card
          icon={<Coins className="h-4 w-4" />}
          label={t("home.balance", lang)}
          value={`Rp ${me.balance.toLocaleString("id-ID")}`}
        />
        <Card
          icon={<Gauge className="h-4 w-4" />}
          label={t("home.quota", lang)}
          value={`${me.quota.used} / ${me.quota.limit}`}
        />
        <Card
          icon={<Flame className="h-4 w-4" />}
          label={t("home.streak", lang)}
          value={String(me.checkin?.streak ?? 0)}
        />
        <Card
          icon={<Crown className="h-4 w-4" />}
          label={me.premium ? t("home.premium", lang) : t("home.free", lang)}
          value={me.premium?.plan_name || "—"}
        />
      </div>

      <Link
        href="/app/generate/"
        className="mt-6 flex min-h-[48px] items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground"
      >
        <Sparkles className="h-4 w-4" />
        {t("home.genCta", lang)}
      </Link>
      <p className="mt-3 text-center text-xs text-muted-foreground">{t("home.soon", lang)}</p>
    </AppShell>
  );
}

function Card({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="truncate text-lg font-semibold">{value}</div>
    </div>
  );
}
