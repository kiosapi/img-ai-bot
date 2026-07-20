"use client";
import { useEffect, useState } from "react";
import { AlertTriangle, Download, XCircle, PartyPopper, Calendar, User } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";
import { useLang } from "@/lib/i18n";

export default function ErrorsPage() {
  const { t, lang } = useLang();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api("/api/errors").then(setD).catch((e) => setErr(String(e?.message || e))); }, []);
  if (err) return <div className="py-20 text-center text-destructive text-sm">{err}</div>;
  if (!d) return <div className="py-20 text-center text-muted-foreground">{t("common.loading")}</div>;

  const errorsArr: any[] = Array.isArray(d.errors) ? d.errors : [];
  const failedToday = errorsArr.filter((e: any) => { try { const dt = new Date(e.created_at); const today = new Date(); return dt.toDateString() === today.toDateString(); } catch { return false; } }).length;

  return (
    <div className="flex flex-col gap-5">
      <div><h1 className="text-2xl font-bold tracking-tight">{t("errors.title")}</h1><p className="text-sm text-muted-foreground">{t("errors.sub")}</p></div>

      <div className="grid grid-cols-2 gap-4">
        <Card><CardContent className="pt-5"><div className="text-3xl font-extrabold text-destructive">{errorsArr.length}</div><div className="text-xs text-muted-foreground mt-1">{t("errors.total_failed")}</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-3xl font-extrabold text-amber-500">{failedToday}</div><div className="text-xs text-muted-foreground mt-1">{t("errors.failed_today")}</div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle><AlertTriangle className="h-4 w-4" />{t("errors.failure_list")} <span className="text-muted-foreground font-normal">{t("errors.count_suffix", { n: errorsArr.length })}</span></CardTitle></CardHeader>
        <CardContent className="px-0 pt-0">
          {errorsArr.length === 0 && <div className="flex flex-col items-center gap-2 py-12 text-center text-sm text-muted-foreground"><div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15"><PartyPopper className="h-6 w-6 text-emerald-500" /></div><div className="font-medium text-foreground">{t("errors.no_errors")}</div></div>}
          {errorsArr.map((e: any) => (
            <div key={e.id} className="flex items-start gap-3 border-b px-5 py-3 last:border-0">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-red-500/10"><XCircle className="h-4 w-4 text-destructive" /></div>
              <div className="min-w-0 flex-1">
                <div className="text-sm break-words leading-relaxed">{e.prompt ? <span className="text-foreground">{String(e.prompt).slice(0, 200)}</span> : <span className="text-muted-foreground italic">{t("errors.no_prompt")}</span>}</div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><User className="h-3 w-3" />{e.user_id ? `ID ${e.user_id}` : "-"}</span>
                  <span className="inline-flex items-center gap-1"><Calendar className="h-3 w-3" />{e.created_at ? new Date(e.created_at).toLocaleString(lang === "id" ? "id-ID" : "en-US") : "-"}</span>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Download className="h-4 w-4" />{t("errors.export_csv")}</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Button variant="outline" className="flex-1" onClick={() => window.open(`/api/export/users.csv?_t=${Date.now()}`, "_blank")}><Download className="h-4 w-4" />{t("errors.export_users")}</Button>
          <Button variant="outline" className="flex-1" onClick={() => window.open(`/api/export/generations.csv?_t=${Date.now()}`, "_blank")}><Download className="h-4 w-4" />{t("errors.export_gens")}</Button>
        </CardContent>
      </Card>
    </div>
  );
}
