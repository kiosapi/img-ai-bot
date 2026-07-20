"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { ScrollText, Bot, Server, Database, Globe, Copy, Pause, Play, Trash2, Search, AlertTriangle, Info, Bug, Terminal, RefreshCw, Check, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CustomSelect } from "@/components/ui/modal";
import { useLang } from "@/lib/i18n";

type LogType = "bot" | "api" | "postgres" | "web";
type LogLevel = "all" | "info" | "warn" | "error" | "debug";
interface LogLine { line: string; level: string; idx: number; }
interface TailResp { type: string; lines_requested: number; lines_returned: number; source: string; container: string | null; docker_error: string; logs: LogLine[]; raw?: string; }

const TYPE_TABS: { id: LogType; labelId: string; labelEn: string; icon: any }[] = [
  { id: "bot", labelId: "Bot", labelEn: "Bot", icon: Bot },
  { id: "api", labelId: "API", labelEn: "API", icon: Server },
  { id: "postgres", labelId: "DB", labelEn: "DB", icon: Database },
  { id: "web", labelId: "Web", labelEn: "Web", icon: Globe },
];
const LEVEL_OPTS: { id: LogLevel; label: string; icon: any }[] = [
  { id: "all", label: "All", icon: Terminal },
  { id: "error", label: "Error", icon: AlertTriangle },
  { id: "warn", label: "Warn", icon: AlertTriangle },
  { id: "info", label: "Info", icon: Info },
  { id: "debug", label: "Debug", icon: Bug },
];

export default function LogsPage() {
  const { lang } = useLang();
  const [type, setType] = useState<LogType>("bot");
  const [level, setLevel] = useState<LogLevel>("all");
  const [lines, setLines] = useState<number>(200);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [data, setData] = useState<TailResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [auto, setAuto] = useState(true);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const autoRef = useRef(auto); autoRef.current = auto;

  const fetchLogs = useCallback(async (showLoader = true) => {
    if (showLoader) setLoading(true); setError(null);
    try {
      const qs = new URLSearchParams({ type, lines: String(lines), level, search }).toString();
      const resp = await api(`/api/logs/tail?${qs}`) as TailResp; setData(resp);
    } catch (e: any) { setError(e?.message || "Failed to fetch logs"); } finally { if (showLoader) setLoading(false); }
  }, [type, lines, level, search]);

  useEffect(() => { fetchLogs(true); }, [fetchLogs]);
  useEffect(() => { if (!auto) return; const id = setInterval(() => { if (autoRef.current) fetchLogs(false); }, 5000); return () => clearInterval(id); }, [auto, fetchLogs]);
  useEffect(() => { const t = setTimeout(() => setSearch(searchInput.trim()), 400); return () => clearTimeout(t); }, [searchInput]);

  const handleCopy = async () => {
    if (!data?.logs?.length) return;
    const text = data.logs.map(l => l.line).join("\n");
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {}
  };

  const isRealtime = data?.source?.startsWith("docker-") && data.source.includes("real");
  const isFallback = data?.source?.includes("fallback") || data?.source?.includes("NOT real");

  return (
    <div className="flex flex-col gap-4 w-full max-w-full overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 w-full">
        <div className="min-w-0"><h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2"><ScrollText className="h-5 w-5 sm:h-6 sm:w-6" />{lang === "id" ? "Live Logs" : "Live Logs"}</h1><p className="text-xs sm:text-sm text-muted-foreground mt-1">{isRealtime ? <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />REALTIME via docker.sock</span> : isFallback ? <span className="text-amber-600">FALLBACK — bukan real docker logs</span> : "Docker logs realtime + auto-refresh 5s"}</p></div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Button variant={auto ? "default" : "outline"} size="sm" onClick={() => setAuto(v => !v)} className="h-8 text-xs">{auto ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}{auto ? "Auto ON" : "Paused"}</Button>
          <Button variant="outline" size="sm" onClick={() => fetchLogs(true)} disabled={loading} className="h-8 w-8 p-0"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></Button>
          <Button variant="outline" size="sm" onClick={handleCopy} disabled={!data?.logs?.length} className="h-8 text-xs">{copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}{copied ? "Copied" : "Copy"}</Button>
        </div>
      </div>

      {data?.docker_error && !isRealtime && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-200 flex gap-2 items-start"><AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" /><div><div className="font-semibold">Docker log error</div><div className="break-all">{data.docker_error}</div><div className="mt-1 opacity-70">Fix: mount <code className="bg-black/10 px-1 rounded">/var/run/docker.sock:/var/run/docker.sock:ro</code> di compose api service — sudah di-fix di docker-compose.yml terbaru.</div></div></div>
      )}

      <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-none">
        {TYPE_TABS.map(t => {
          const active = type === t.id;
          return (
            <button key={t.id} onClick={() => setType(t.id)} className={`flex items-center gap-1.5 rounded-full border px-3 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm font-medium transition-colors shrink-0 ${active ? "bg-primary text-primary-foreground border-primary shadow" : "bg-card hover:bg-accent"}`}>
              <t.icon className="h-3.5 w-3.5" />{lang === "id" ? t.labelId : t.labelEn}
            </button>
          );
        })}
      </div>

      <Card className="w-full max-w-full overflow-hidden">
        <CardHeader className="p-3 sm:p-5 pb-2 flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-sm sm:text-base flex flex-wrap items-center gap-2"><Terminal className="h-4 w-4" />{type.toUpperCase()} LOGS {data && <span className="text-[11px] font-normal text-muted-foreground flex items-center gap-1">· {data.lines_returned} lines · {isRealtime ? <span className="inline-flex items-center gap-1"><CheckCircle2 className="h-3 w-3 text-emerald-500" />real</span> : <span className="inline-flex items-center gap-1"><AlertTriangle className="h-3 w-3 text-amber-500" />fallback</span>} {data.container ? `(${data.container})` : ""}</span>}</CardTitle>
            {isFallback && <span className="text-[11px] bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/20 rounded px-2 py-1 flex items-center gap-1"><AlertTriangle className="h-3 w-3" />{data?.source?.slice(0, 60)}</span>}
          </div>
          <div className="flex flex-wrap items-center gap-2 overflow-x-auto">
            <div className="flex items-center gap-1 rounded-full border bg-muted/30 p-0.5 shrink-0">{LEVEL_OPTS.map(o => { const active = level === o.id; return (<button key={o.id} onClick={() => setLevel(o.id as LogLevel)} className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] sm:text-xs font-medium transition shrink-0 ${active ? "bg-card shadow border text-foreground" : "text-muted-foreground hover:text-foreground"}`}><o.icon className={`h-3 w-3 ${active ? (o.id === "error" ? "text-red-500" : o.id === "warn" ? "text-amber-500" : "") : ""}`} />{o.label}</button>); })}</div>
            <CustomSelect value={String(lines)} onChange={v=>setLines(Number(v))} options={[{value:"100",label:"100 lines"},{value:"200",label:"200 lines"},{value:"300",label:"300 lines"},{value:"500",label:"500 lines"}]} className="w-[110px] shrink-0" />
            <div className="relative flex-1 min-w-[140px] max-w-[220px]"><Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" /><input value={searchInput} onChange={e => setSearchInput(e.target.value)} placeholder={lang === "id" ? "Filter..." : "Filter..."} className="h-7 sm:h-8 w-full rounded-md border bg-background pl-7 pr-7 text-xs sm:text-sm outline-none focus:ring-1 focus:ring-ring" />{searchInput && <button onClick={() => setSearchInput("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"><Trash2 className="h-3.5 w-3.5" /></button>}</div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {error && <div className="flex items-center gap-2 px-4 py-3 text-xs text-destructive bg-destructive/5 border-y"><AlertTriangle className="h-4 w-4" />{error}</div>}
          {loading && !data ? <div className="py-14 text-center text-sm text-muted-foreground flex flex-col items-center gap-2"><RefreshCw className="h-5 w-5 animate-spin" />{lang === "id" ? "Memuat logs..." : "Loading logs..."}</div> : (
            <div className="max-h-[65vh] overflow-auto bg-[#0a0a0a] text-[11px] sm:text-[12px] leading-5 sm:leading-6 font-mono">
              {!data?.logs?.length ? <div className="py-10 text-center text-muted-foreground"><Terminal className="mx-auto h-6 w-6 mb-2 opacity-40" /><div className="text-xs">{lang === "id" ? "Tidak ada log" : "No logs"}</div><div className="text-[11px] mt-1 opacity-60 max-w-xs mx-auto break-words">{isFallback ? (lang === "id" ? "Docker tidak tersedia, menampilkan fallback DB. Setelah deploy docker.sock fix ini akan jadi realtime." : "Docker unavailable, showing DB fallback. After deploy with docker.sock mount it will be realtime.") : (lang === "id" ? "Container belum menulis log" : "Container has no logs yet")}</div></div> : (
                <div className="divide-y divide-white/[0.06] w-full max-w-full">
                  {data.logs.map((l, i) => (
                    <div key={i} className={`flex gap-2 px-2 sm:px-3 py-1 sm:py-1.5 w-full max-w-full overflow-hidden ${l.level === "error" ? "bg-red-500/[0.08] border-l-2 border-l-red-500/60" : l.level === "warn" ? "bg-amber-500/[0.06] border-l-2 border-l-amber-500/50" : "border-l-2 border-l-transparent"} hover:bg-white/[0.04] transition-colors`}>
                      <span className="shrink-0 select-none text-white/25 text-[9px] sm:text-[10px] w-6 sm:w-8 text-right pt-0.5">{l.idx + 1}</span>
                      <span className={`shrink-0 rounded px-1 sm:px-1.5 py-0 text-[8px] sm:text-[9px] font-bold uppercase leading-4 tracking-wide border h-fit mt-0.5 ${l.level === "error" ? "bg-red-500/20 text-red-300 border-red-500/30" : l.level === "warn" ? "bg-amber-500/20 text-amber-300 border-amber-500/30" : l.level === "debug" ? "bg-zinc-700/60 text-zinc-400 border-white/10" : "bg-blue-500/15 text-blue-300 border-blue-500/20"}`}>{l.level}</span>
                      <span className={`flex-1 min-w-0 break-all whitespace-pre-wrap ${l.level === "error" ? "text-red-200" : l.level === "warn" ? "text-amber-100" : "text-zinc-200"}`}>{l.line}</span>
                    </div>
                  ))}<div ref={bottomRef} />
                </div>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t bg-muted/20 px-3 py-1.5 text-[10px] sm:text-xs text-muted-foreground"><div className="flex items-center gap-2"><span className="inline-flex items-center gap-1">{isRealtime ? <><CheckCircle2 className="h-3 w-3 text-emerald-500" />real docker</> : isFallback ? <><AlertTriangle className="h-3 w-3 text-amber-500" />fallback DB</> : "docker"} · {data?.source?.slice(0, 50)}</span></div><div className="flex items-center gap-2">{auto && <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />live 5s</span>}<span>{data ? `${data.lines_returned}/${data.lines_requested}` : ""}</span></div></div>
        </CardContent>
      </Card>
    </div>
  );
}
