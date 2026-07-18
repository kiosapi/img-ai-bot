"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Users, ImageIcon, Zap, TrendingUp, CheckCircle2, XCircle } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/controls";

const stat = (icon: any, label: string, color: string) => ({ icon, label, color });
const STATS = [
  stat(Users, "Total User", "text-blue-500"),
  stat(ImageIcon, "Gambar Hari Ini", "text-emerald-500"),
  stat(Zap, "User Aktif", "text-amber-500"),
  stat(TrendingUp, "Total Gambar", "text-violet-500"),
];

export default function Home() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [chart, setChart] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([api("/api/stats"), api("/api/chart")])
      .then(([s, c]) => { setData(s); setChart(c); })
      .catch(() => router.push("/login"));
  }, [router]);

  if (!data) return <div className="py-20 text-center text-muted-foreground">Memuat...</div>;
  const values = [data.total_users, data.today_gen, data.active_today, data.total_gen];

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Ringkasan aktivitas bot</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {STATS.map((s, i) => (
          <Card key={i}>
            <CardContent className="pt-5">
              <s.icon className={`h-6 w-6 ${s.color}`} />
              <div className="mt-3 text-3xl font-extrabold tracking-tight">{values[i]}</div>
              <div className="mt-1 text-sm text-muted-foreground">{s.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle><TrendingUp className="h-4 w-4" />Aktivitas 7 Hari</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={chart} margin={{ left: -20, right: 8, top: 8 }}>
              <defs>
                <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="day" stroke="var(--muted-foreground)" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis stroke="var(--muted-foreground)" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 13 }} />
              <Area type="monotone" dataKey="gen" name="Gambar" stroke="var(--primary)" strokeWidth={3} fill="url(#g)" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Zap className="h-4 w-4" />Aktivitas Terbaru</CardTitle></CardHeader>
        <CardContent className="flex flex-col">
          {data.recent.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">Belum ada aktivitas</div>}
          {data.recent.map((g: any, i: number) => (
            <div key={i} className="flex items-center gap-3 border-b py-3 last:border-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-sm font-bold text-white">
                {(g.username || "U")[0].toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{g.username ? "@" + g.username : g.user_id}</div>
                <div className="truncate text-xs text-muted-foreground">{g.kind} · {(g.prompt || "").slice(0, 40)}</div>
              </div>
              {g.success
                ? <Badge variant="success"><CheckCircle2 className="h-3 w-3" />ok</Badge>
                : <Badge variant="destructive"><XCircle className="h-3 w-3" />gagal</Badge>}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
