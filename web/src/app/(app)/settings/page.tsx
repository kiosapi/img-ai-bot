"use client";
import { useEffect, useState } from "react";
import { Settings2, Wrench, Info } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Switch } from "@/components/ui/controls";

export default function SettingsPage() {
  const [limit, setLimit] = useState(20);
  const [maint, setMaint] = useState(false);
  const [info, setInfo] = useState<any>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api("/api/settings").then((s) => {
      setLimit(s.daily_limit); setMaint(s.maintenance); setInfo(s);
    }).catch(() => {});
  }, []);

  async function save() {
    setLoading(true);
    try {
      await api("/api/settings", { method: "POST", body: JSON.stringify({ daily_limit: Number(limit), maintenance: maint }) });
      toast.success("Pengaturan disimpan");
    } catch { toast.error("Gagal menyimpan"); }
    finally { setLoading(false); }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Pengaturan</h1>
        <p className="text-sm text-muted-foreground">Konfigurasi bot</p>
      </div>

      <Card>
        <CardHeader><CardTitle><Settings2 className="h-4 w-4" />Limit & Mode</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium">Limit Harian per User</label>
            <Input type="number" min={0} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
          </div>
          <div className="flex items-center gap-3 border-t pt-4">
            <Wrench className="h-5 w-5 text-amber-500" />
            <div className="flex-1">
              <div className="text-sm font-semibold">Mode Maintenance</div>
              <div className="text-xs text-muted-foreground">Sementara nonaktifkan bot untuk user</div>
            </div>
            <Switch checked={maint} onChange={setMaint} />
          </div>
        </CardContent>
      </Card>

      <Button onClick={save} disabled={loading}>{loading ? "Menyimpan..." : "Simpan Pengaturan"}</Button>

      <Card>
        <CardHeader><CardTitle><Info className="h-4 w-4" />Info</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm">
          <div className="flex justify-between"><span className="text-muted-foreground">Channel Wajib</span><span className="font-medium">{info.channel || "—"}</span></div>
          <div className="flex justify-between"><span className="text-muted-foreground">Model</span><span className="font-medium">{info.model}</span></div>
        </CardContent>
      </Card>
    </div>
  );
}
