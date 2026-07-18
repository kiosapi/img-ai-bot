"use client";
import { useState } from "react";
import { Send, Info } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/controls";

export default function BroadcastPage() {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!message.trim()) return toast.error("Pesan kosong");
    if (!confirm("Kirim ke semua user?")) return;
    setLoading(true);
    try {
      const r = await api("/api/broadcast", { method: "POST", body: JSON.stringify({ message }) });
      toast.success(`Terkirim ke ${r.sent}/${r.total} user`);
      setMessage("");
    } catch { toast.error("Gagal broadcast"); }
    finally { setLoading(false); }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Broadcast</h1>
        <p className="text-sm text-muted-foreground">Kirim pesan ke semua user</p>
      </div>

      <Card>
        <CardHeader><CardTitle><Send className="h-4 w-4" />Pesan Baru</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Textarea rows={5} placeholder="Tulis pesan... (mendukung HTML: <b>, <i>, <a>)" value={message} onChange={(e) => setMessage(e.target.value)} />
          <Button onClick={send} disabled={loading}><Send className="h-4 w-4" />{loading ? "Mengirim..." : "Kirim Sekarang"}</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Info className="h-4 w-4" />Info</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground leading-relaxed">
          Pesan dikirim ke semua user yang tidak dibanned. User yang memblokir bot akan otomatis dilewati.
        </CardContent>
      </Card>
    </div>
  );
}
