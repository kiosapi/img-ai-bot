"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, XCircle, ImageIcon, Ban } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/controls";

export default function UserDetail() {
  const { id } = useParams();
  const router = useRouter();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    api(`/api/users/${id}`).then(setData).catch(() => { toast.error("User tidak ditemukan"); router.push("/users"); });
  }, [id, router]);

  async function toggleBan() {
    try {
      await api("/api/users/ban", { method: "POST", body: JSON.stringify({ user_id: Number(id), banned: !data.user.is_banned }) });
      toast.success(data.user.is_banned ? "User di-unban" : "User dibanned");
      setData((d: any) => ({ ...d, user: { ...d.user, is_banned: !d.user.is_banned } }));
    } catch { toast.error("Gagal"); }
  }

  if (!data) return <div className="py-20 text-center text-muted-foreground">Memuat...</div>;
  const u = data.user;

  return (
    <div className="flex flex-col gap-5">
      <Link href="/users" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground w-fit">
        <ArrowLeft className="h-4 w-4" />Kembali ke daftar user
      </Link>

      <Card>
        <CardContent className="pt-5">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-2xl font-bold text-white">
              {(u.username || u.first_name || "U")[0].toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xl font-bold truncate">
                {u.username ? "@" + u.username : (u.first_name || "User")}
                {u.is_banned && <Badge variant="destructive" className="ml-2">banned</Badge>}
              </div>
              <div className="text-sm text-muted-foreground">ID {u.user_id}</div>
              {u.first_name && <div className="text-sm text-muted-foreground">{u.first_name}</div>}
            </div>
            <Button size="sm" variant={u.is_banned ? "success" : "destructive"} onClick={toggleBan}>
              {u.is_banned ? <><CheckCircle2 className="h-4 w-4" />Unban</> : <><Ban className="h-4 w-4" />Ban</>}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold">{data.total}</div><div className="text-xs text-muted-foreground mt-1">Total Gambar</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-emerald-500">{data.success}</div><div className="text-xs text-muted-foreground mt-1">Berhasil</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-destructive">{data.failed}</div><div className="text-xs text-muted-foreground mt-1">Gagal</div></CardContent></Card>
        <Card><CardContent className="pt-5"><div className="text-2xl font-extrabold text-amber-500">{data.today}</div><div className="text-xs text-muted-foreground mt-1">Hari Ini</div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle><ImageIcon className="h-4 w-4" />Riwayat Generate ({data.generations.length})</CardTitle></CardHeader>
        <CardContent className="px-0 pt-0">
          {data.generations.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">Belum ada aktivitas</div>}
          {data.generations.map((g: any, i: number) => (
            <div key={i} className="flex items-start gap-3 border-b px-5 py-3 last:border-0">
              <Badge variant={g.kind === "edit" ? "default" : "muted"} className="mt-0.5 shrink-0">{g.kind}</Badge>
              <div className="min-w-0 flex-1">
                <div className="text-sm break-words">{g.prompt || <span className="text-muted-foreground italic">tanpa prompt</span>}</div>
                <div className="text-xs text-muted-foreground mt-0.5">{g.size} · {new Date(g.created_at).toLocaleString("id-ID")}</div>
              </div>
              {g.success
                ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                : <XCircle className="h-4 w-4 shrink-0 text-destructive mt-0.5" />}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
