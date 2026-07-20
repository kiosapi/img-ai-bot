"use client";
import { useEffect, useState } from "react";
import { Clock, TrendingUp, Trophy, PieChart as PieIcon } from "lucide-react";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";

const KIND_COLORS: Record<string, string> = { generate: "#0a84ff", edit: "#a855f7" };

export default function AnalyticsPage() {
  const { t } = useLang();
  const [d, setD] = useState<any>(null);
  useEffect(() => { api("/api/analytics").then(setD).catch(() => {}); }, []);
  if (!d) return <div className="py-20 text-center text-muted-foreground">{t("common.loading")}</div>;

  const totalKinds = d.kinds.reduce((a: number, k: any) => a + k.c, 0) || 1;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("analytics.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("analytics.sub")}</p>
      </div>

      <Card>
        <CardHeader><CardTitle><Clock className="h-4 w-4" />{t("analytics.busy_hours")}</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.hours} margin={{ left: -20, right: 8, top: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="hour" stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} interval={2} />
              <YAxis stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 13 }} labelFormatter={(h:any)=>t("analytics.hour_label",{h})} />
              <Bar dataKey="count" name={t("analytics.images")} fill="var(--primary)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle><TrendingUp className="h-4 w-4" />{t("analytics.success_rate")}</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={d.daily_success} margin={{ left: -20, right: 8, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="day" stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} domain={[0, 100]} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 13 }} formatter={(v:any)=>[`${v}%`, "Success"]} />
                <Line type="monotone" dataKey="rate" stroke="#10b981" strokeWidth={3} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle><PieIcon className="h-4 w-4" />{t("analytics.activity_type")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-3 pt-2">
            {d.kinds.map((k: any) => {
              const pct = Math.round((k.c / totalKinds) * 100);
              return (
                <div key={k.kind}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium capitalize">{k.kind}</span>
                    <span className="text-muted-foreground">{k.c} ({pct}%)</span>
                  </div>
                  <div className="h-2.5 w-full rounded-full bg-muted overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: KIND_COLORS[k.kind] || "#8e8e93" }} />
                  </div>
                </div>
              );
            })}
            {d.kinds.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">{t("analytics.no_data")}</div>}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle><Trophy className="h-4 w-4" />{t("analytics.top_prompts")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2 pt-0">
            {d.top_prompts.map((p: any, i: number) => (
              <div key={i} className="flex items-start gap-2 border-b py-2 last:border-0 text-sm">
                <span className="text-muted-foreground w-5 shrink-0">{i + 1}.</span>
                <span className="flex-1 break-words">{p.prompt.slice(0, 60)}</span>
                <Badge variant="default" className="shrink-0">{p.c}x</Badge>
              </div>
            ))}
            {d.top_prompts.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">{t("analytics.no_data")}</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle><Trophy className="h-4 w-4" />{t("analytics.top_users")}</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-2 pt-0">
            {d.top_users.map((u: any, i: number) => (
              <div key={i} className="flex items-center gap-2 border-b py-2 last:border-0 text-sm">
                <span className="text-muted-foreground w-5 shrink-0">{i + 1}.</span>
                <span className="flex-1 truncate">{u.username ? "@" + u.username : u.user_id}</span>
                <Badge variant="success" className="shrink-0">{u.c} {t("analytics.images")}</Badge>
              </div>
            ))}
            {d.top_users.length === 0 && <div className="py-6 text-center text-sm text-muted-foreground">{t("analytics.no_data")}</div>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
