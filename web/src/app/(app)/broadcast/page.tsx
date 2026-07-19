"use client";
import { useEffect, useState } from "react";
import { Send, Info, Users, Crown, UserCheck, Eye, History, Bold, Italic, Link2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea, Badge } from "@/components/ui/controls";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

const AUDIENCES = [
  { v: "all", label: "Semua User", icon: Users },
  { v: "premium", label: "Premium Aktif", icon: Crown },
  { v: "free", label: "Free (non-premium)", icon: UserCheck },
];
const MAX_LEN = 4096;

/** Very small HTML-subset renderer just for the live preview (bold/italic/link only). */
function renderPreview(text: string) {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const html = escaped
    .replace(/&lt;b&gt;(.*?)&lt;\/b&gt;/gs, "<b>$1</b>")
    .replace(/&lt;i&gt;(.*?)&lt;\/i&gt;/gs, "<i>$1</i>")
    .replace(/&lt;a href=(?:&quot;|")(.*?)(?:&quot;|")&gt;(.*?)&lt;\/a&gt;/gs, '<a href="$1" class="underline text-primary" target="_blank" rel="noreferrer">$2</a>')
    .replace(/\n/g, "<br/>");
  return { __html: html };
}

export default function BroadcastPage() {
  const [message, setMessage] = useState("");
  const [audience, setAudience] = useState("all");
  const [loading, setLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [counts, setCounts] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    api("/api/broadcast/audience-counts").then(setCounts).catch(() => {});
    api("/api/broadcast/history").then((d) => setHistory(d.history || [])).catch(() => {});
  }, []);

  const targetCount = counts ? (counts[audience] ?? counts.all) : null;
  const audienceLabel = AUDIENCES.find((a) => a.v === audience)?.label || "Semua User";
  const remaining = MAX_LEN - message.length;

  function wrap(tag: "b" | "i") {
    setMessage((m) => `${m}<${tag}></${tag}>`);
  }
  function insertLink() {
    setMessage((m) => `${m}<a href="https://">teks link</a>`);
  }

  async function doSend() {
    setLoading(true);
    try {
      const r = await api("/api/broadcast", { method: "POST", body: JSON.stringify({ message, audience }) });
      toast.success(`Terkirim ke ${r.sent}/${r.total} user (${audienceLabel})`);
      setMessage("");
      setConfirmOpen(false);
      api("/api/broadcast/history").then((d) => setHistory(d.history || [])).catch(() => {});
    } catch (e: any) { toast.error(e.message || "Gagal broadcast"); }
    finally { setLoading(false); }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Broadcast</h1>
        <p className="text-sm text-muted-foreground">Kirim pesan ke user bot</p>
      </div>

      <Card>
        <CardHeader><CardTitle><Users className="h-4 w-4" />Target Audience</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 sm:flex-row">
          {AUDIENCES.map((a) => (
            <button
              key={a.v}
              onClick={() => setAudience(a.v)}
              className={`flex flex-1 items-center gap-2 rounded-md border px-3 py-2.5 text-sm font-medium transition-colors ${audience === a.v ? "border-primary bg-primary/10 text-primary" : "hover:bg-accent"}`}
            >
              <a.icon className="h-4 w-4" />
              {a.label}
              <Badge variant="muted" className="ml-auto">{counts ? counts[a.v] : "…"}</Badge>
            </button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><Send className="h-4 w-4" />Pesan Baru</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => wrap("b")}><Bold className="h-3.5 w-3.5" />Bold</Button>
            <Button type="button" size="sm" variant="outline" onClick={() => wrap("i")}><Italic className="h-3.5 w-3.5" />Italic</Button>
            <Button type="button" size="sm" variant="outline" onClick={insertLink}><Link2 className="h-3.5 w-3.5" />Link</Button>
          </div>
          <Textarea rows={5} placeholder="Tulis pesan... (mendukung HTML: <b>, <i>, <a>)" value={message} onChange={(e) => setMessage(e.target.value.slice(0, MAX_LEN))} />
          <div className={`text-right text-xs ${remaining < 100 ? "text-destructive" : "text-muted-foreground"}`}>{message.length}/{MAX_LEN} karakter</div>

          {message.trim() && (
            <div>
              <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Eye className="h-3.5 w-3.5" />Preview</div>
              <div className="rounded-md border bg-muted/40 p-3 text-sm leading-relaxed" dangerouslySetInnerHTML={renderPreview(message)} />
            </div>
          )}

          <Button onClick={() => { if (!message.trim()) return toast.error("Pesan kosong"); setConfirmOpen(true); }} disabled={loading}>
            <Send className="h-4 w-4" />{loading ? "Mengirim..." : `Kirim ke ${audienceLabel}`}
          </Button>
        </CardContent>
      </Card>

      {history.length > 0 && (
        <Card>
          <CardHeader><CardTitle><History className="h-4 w-4" />Riwayat Broadcast</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-0 px-0 pt-0">
            {history.map((h: any, i: number) => (
              <div key={i} className="flex items-start gap-3 border-b px-5 py-3 last:border-0">
                <Badge variant="muted" className="mt-0.5 shrink-0">{AUDIENCES.find(a => a.v === h.audience)?.label || h.audience}</Badge>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{h.message}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{h.sent}/{h.total} terkirim · {new Date(h.created_at).toLocaleString("id-ID")}</div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle><Info className="h-4 w-4" />Info</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground leading-relaxed">
          Pesan dikirim ke user pada audience terpilih yang tidak dibanned. User yang memblokir bot akan otomatis dilewati.
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={doSend}
        loading={loading}
        title="Kirim Broadcast"
        variant="destructive"
        confirmLabel="Ya, Kirim"
        description={<>Pesan akan dikirim ke <b className="text-foreground">{targetCount ?? "…"}</b> user pada target <b className="text-foreground">{audienceLabel}</b>. Aksi ini tidak bisa dibatalkan setelah dikirim.</>}
      />
    </div>
  );
}
