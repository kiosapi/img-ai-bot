"use client";
import { useEffect, useState } from "react";
import { AlertTriangle, Download, XCircle } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";

export default function ErrorsPage() {
  const [d, setD] = useState<any>(null);

  useEffect(() => { api("/api/errors").then(setD).catch(() => {}); }, []);
  if (!d) return <div className="py-20 text-center text-muted-foreground">Memuat...</div>;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Log Error</h1>
        <p className="text-sm text-muted-foreground">Generate yang gagal</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card><CardContent className="pt-5"><div className="text-3xl font-extrabold text-destructive">{d.total_failed}</div><div className="text-xs text-muted-foreground mt-1">Total Gagal</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-3xl font-extrabold text-amber-500">{d.failed_today}</div><div className="text-xs text-muted-foreground mt-1">Gagal Hari Ini</div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle><AlertTriangle className="h-4 w-4" />Daftar Kegagalan ({d.errors.length})</CardTitle></CardHeader>
        <CardContent className="px-0 pt-0">
          {d.errors.length === 0 && <div className="py-10 text-center text-sm text-muted-foreground">🎉 Tidak ada error — semua generate berhasil!</div>}
          {d.errors.map((e: any) => (
            <div key={e.id} className="flex items-start gap-3 border-b px-5 py-3 last:border-0">
              <XCircle className="h-4 w-4 shrink-0 text-destructive mt-0.5" />
              <div className="min-w-0 flex-1">
                <div className="text-sm break-words">{e.prompt || <span className="text-muted-foreground italic">tanpa prompt</span>}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  <Badge variant="muted" className="mr-1">{e.kind}</Badge>
                  {e.username ? "@" + e.username : e.user_id} · {new Date(e.created_at).toLocaleString("id-ID")}
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Download className="h-4 w-4" />Export Data (CSV)</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <a href="/api/export/users.csv" className="flex-1">
            <Button variant="outline" className="w-full"><Download className="h-4 w-4" />Export User</Button>
          </a>
          <a href="/api/export/generations.csv" className="flex-1">
            <Button variant="outline" className="w-full"><Download className="h-4 w-4" />Export Generasi</Button>
          </a>
        </CardContent>
      </Card>
    </div>
  );
}
