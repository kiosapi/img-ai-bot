"use client";
import { useEffect, useState } from "react";
import { Clock, TrendingUp, Trophy, PieChart as PieIcon, AlertTriangle } from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";
import { PageLoader } from "@/components/ui/page-loader";

const KIND_COLORS: Record<string, string> = { generate: "#0a84ff", edit: "#a855f7" };

export default function AnalyticsPage() {
  const { t, lang } = useLang();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api("/api/analytics").then(setD).catch((e) => setErr(String(e?.message || e)));
  }, []);
  if (err) return <div className="py-20 text-center text-destructive text-sm">{err}</div>;
  if (!d) return <PageLoader label={t("common.loading")} cards={4} rows={3} />;

  const hours = Array.isArray(d.hours) ? d.hours : [];
  const daily = Array.isArray(d.daily) ? d.daily : [];
  const topPrompts = Array.isArray(d.top_prompts) ? d.top_prompts : [];
  const errorsList = Array.isArray(d.errors) ? d.errors : [];
  const totalGen = daily.reduce((a: number, x: any) => a + (x.gen || 0), 0) || 1;

  return (
    <div className="flex flex-col gap-5">
      <div><h1 className="text-2xl font-bold tracking-tight">{t("analytics.title")}</h1><p className="text-sm text-muted-foreground">{t("analytics.sub")}</p></div>

      <Card>
        <CardHeader><CardTitle><Clock className="h-4 w-4" />{t("analytics.busy_hours")}</CardTitle></CardHeader>
        <CardContent>
          {hours.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">{t("analytics.no_data")}</div> : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={hours.map((h: any) => ({ hour: `h ${h.h}:00`, label: h.h, count: h.c }))} margin={{ left: -20, right: 8, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="label" stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} interval={2} />
                <YAxis stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 13 }} labelFormatter={(l: any) => t("analytics.hour_label", { h: l })} />
                <Bar dataKey="count" name={t("analytics.images")} fill="var(--primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle><TrendingUp className="h-4 w-4" />{lang === "id" ? " Tren Harian (30 hari)" : " Daily Trend (30 days)"}</CardTitle></CardHeader>
          <CardContent>
            {daily.length === 0 ? <div className="py-10 text-center text-sm text-muted-foreground">{t("analytics.no_data")}</div> : (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={daily} margin={{ left: -20, right: 8, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="day" stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v: string) => v.slice(5)} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 13 }} />
                  <Line type="monotone" dataKey="gen" stroke="#0a84ff" strokeWidth={3} dot={false} name={t("analytics.images")} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle><PieIcon className="h-4 w-4" />{lang === "id" ? "Status Generasi" : "Generation Status"}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-3 pt-2">
            <div><div className="flex justify-between text-sm mb-1"><span className="font-medium">{lang === "id" ? "Total Generate 30 hari" : "Total 30d"}</span><span className="text-muted-foreground">{totalGen - 1 + daily.length}</span></div><div className="h-2.5 w-full rounded-full bg-muted overflow-hidden"><div className="h-full rounded-full bg-primary" style={{ width: "100%" }} /></div></div>
            {errorsList.length > 0 && <div className="mt-2 text-xs text-destructive flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5" />{errorsList.length} {lang === "id" ? "error terbaru" : "recent errors"}</div>}
            {daily.length === 0 && errorsList.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">{t("analytics.no_data")}</div>}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle><Trophy className="h-4 w-4" />{t("analytics.top_prompts")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2 pt-0">
            {topPrompts.map((p: any, i: number) => (
              <div key={i} className="flex items-start gap-2 border-b py-2 last:border-0 text-sm">
                <span className="text-muted-foreground w-5 shrink-0">{i + 1}.</span>
                <span className="flex-1 break-words">{String(p.prompt || "").slice(0, 80) || t("errors.no_prompt")}</span>
                <Badge variant="muted" className="shrink-0">{p.c}x</Badge>
              </div>
            ))}
            {topPrompts.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">{t("analytics.no_data")}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle><AlertTriangle className="h-4 w-4" />{lang === "id" ? "Error Terbaru" : "Recent Errors"}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2 pt-0">
            {errorsList.map((e: any, i: number) => (
              <div key={i} className="flex items-start gap-2 border-b py-2 last:border-0 text-sm">
                <span className="text-muted-foreground w-5 shrink-0">{i + 1}.</span>
                <span className="flex-1 break-words">{String(e.prompt || "").slice(0, 80) || t("errors.no_prompt")}</span>
                <span className="text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString(lang === "id" ? "id-ID" : "en-US")}</span>
              </div>
            ))}
            {errorsList.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">{t("errors.no_errors")}</div>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
