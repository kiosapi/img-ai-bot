"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { ScrollText, Bot, Server, Database, Globe, Copy, Pause, Play, Trash2, Search, AlertTriangle, Info, Bug, Terminal, RefreshCw, Check, ShieldCheck } from "lucide-react";
import { api } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useLang } from "@/lib/i18n";

type LogType = "bot" | "api" | "postgres" | "web";
type LogLevel = "all" | "info" | "warn" | "error" | "debug";

interface LogLine {
  line: string;
  level: string;
  idx: number;
}

interface TailResp {
  type: string;
  lines_requested: number;
  lines_returned: number;
  source: string;
  container: string | null;
  docker_error: string;
  logs: LogLine[];
  raw?: string;
}

const TYPE_TABS: { id: LogType; labelId: string; labelEn: string; icon: any }[] = [
  { id: "bot", labelId: "Bot", labelEn: "Bot", icon: Bot },
  { id: "api", labelId: "API", labelEn: "API", icon: Server },
  { id: "postgres", labelId: "Database", labelEn: "Database", icon: Database },
  { id: "web", labelId: "Web", labelEn: "Web", icon: Globe },
];

const LEVEL_OPTS: { id: LogLevel; label: string; icon: any; color: string }[] = [
  { id: "all", label: "All", icon: Terminal, color: "" },
  { id: "error", label: "Error", icon: AlertTriangle, color: "text-red-500" },
  { id: "warn", label: "Warn", icon: AlertTriangle, color: "text-amber-500" },
  { id: "info", label: "Info", icon: Info, color: "text-blue-500" },
  { id: "debug", label: "Debug", icon: Bug, color: "text-muted-foreground" },
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
  const containerRef = useRef<HTMLDivElement>(null);
  const autoRef = useRef(auto);
  autoRef.current = auto;

  const fetchLogs = useCallback(async (showLoader = true) => {
    if (showLoader) setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({
        type,
        lines: String(lines),
        level,
        search,
      }).toString();
      const resp = await api(`/api/logs/tail?${qs}`) as TailResp;
      setData(resp);
    } catch (e: any) {
      setError(e?.message || "Failed to fetch logs");
    } finally {
      if (showLoader) setLoading(false);
    }
  }, [type, lines, level, search]);

  useEffect(() => {
    fetchLogs(true);
  }, [fetchLogs]);

  // auto-refresh 5s
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(() => {
      if (autoRef.current) fetchLogs(false);
    }, 5000);
    return () => clearInterval(id);
  }, [auto, fetchLogs]);

  // debounce search input -> search query
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput.trim()), 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  const handleCopy = async () => {
    if (!data?.logs?.length) return;
    const text = data.logs.map(l => l.line).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const lineColor = (lvl: string) => {
    switch (lvl) {
      case "error": return "text-red-500";
      case "warn": return "text-amber-500";
      case "debug": return "text-muted-foreground";
      default: return "text-foreground";
    }
  };

  const lineBg = (lvl: string) => {
    switch (lvl) {
      case "error": return "bg-red-500/5 border-l-2 border-l-red-500/50";
      case "warn": return "bg-amber-500/5 border-l-2 border-l-amber-500/40";
      default: return "border-l-2 border-l-transparent";
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ScrollText className="h-6 w-6" />
            {lang === "id" ? "Live Logs" : "Live Logs"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {lang === "id"
              ? "Tail log bot/api/postgres — docker logs atau fallback DB errors table. Auto-refresh 5 detik."
              : "Tail bot/api/postgres logs — docker logs or DB errors fallback. Auto-refresh 5s."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant={auto ? "default" : "outline"} size="sm" onClick={() => setAuto(v => !v)}>
            {auto ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {auto ? (lang === "id" ? "Auto ON" : "Auto ON") : (lang === "id" ? "Paused" : "Paused")}
          </Button>
          <Button variant="outline" size="sm" onClick={() => fetchLogs(true)} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button variant="outline" size="sm" onClick={handleCopy} disabled={!data?.logs?.length}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? (lang === "id" ? "Tersalin" : "Copied") : (lang === "id" ? "Copy" : "Copy")}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2">
        {TYPE_TABS.map(t => {
          const active = type === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setType(t.id)}
              className={`flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${active ? "bg-primary text-primary-foreground border-primary shadow" : "bg-card hover:bg-accent"}`}
            >
              <t.icon className="h-4 w-4" />
              {lang === "id" ? t.labelId : t.labelEn}
            </button>
          );
        })}
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-4 w-4" />
              {type.toUpperCase()} LOGS
              {data && <span className="text-xs font-normal lowercase text-muted-foreground">· {data.lines_returned} {lang === "id" ? "baris" : "lines"} · src: {data.source}{data.container ? ` (${data.container})` : ""}</span>}
            </CardTitle>
            {data?.docker_error && (
              <span className="text-xs text-amber-600 bg-amber-500/10 px-2 py-1 rounded">
                docker: {data.docker_error.slice(0, 120)}
              </span>
            )}
          </div>

          {/* Controls row */}
          <div className="flex flex-wrap items-center gap-3">
            {/* level filter */}
            <div className="flex items-center gap-1 rounded-full border bg-muted/30 p-1">
              {LEVEL_OPTS.map(o => {
                const active = level === o.id;
                return (
                  <button
                    key={o.id}
                    onClick={() => setLevel(o.id as LogLevel)}
                    className={`flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium transition ${active ? "bg-card shadow border" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    <o.icon className={`h-3 w-3 ${active ? o.color : ""}`} />
                    {o.label}
                  </button>
                );
              })}
            </div>

            {/* lines selector */}
            <select
              value={lines}
              onChange={e => setLines(Number(e.target.value))}
              className="h-8 rounded-md border bg-background px-2 text-sm"
            >
              <option value={100}>100 lines</option>
              <option value={200}>200 lines</option>
              <option value={300}>300 lines</option>
              <option value={500}>500 lines (max)</option>
            </select>

            {/* search */}
            <div className="relative flex-1 min-w-[180px] max-w-sm">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                placeholder={lang === "id" ? "Filter kata kunci..." : "Filter keyword..."}
                className="h-8 w-full rounded-md border bg-background pl-8 pr-8 text-sm outline-none focus:ring-1 focus:ring-ring"
              />
              {searchInput && (
                <button onClick={() => setSearchInput("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {error && (
            <div className="flex items-center gap-2 px-5 py-4 text-sm text-destructive bg-destructive/5 border-y">
              <AlertTriangle className="h-4 w-4" /> {error}
            </div>
          )}

          {loading && !data ? (
            <div className="py-16 text-center text-sm text-muted-foreground flex flex-col items-center gap-2">
              <RefreshCw className="h-6 w-6 animate-spin" />
              {lang === "id" ? "Memuat logs..." : "Loading logs..."}
            </div>
          ) : (
            <div
              ref={containerRef}
              className="max-h-[62vh] overflow-auto bg-[#0e0e11] dark:bg-[#0a0a0c] text-[12.5px] leading-6 font-mono"
            >
              {!data?.logs?.length ? (
                <div className="py-12 text-center text-muted-foreground">
                  <Terminal className="mx-auto h-8 w-8 mb-2 opacity-40" />
                  <div>{lang === "id" ? "Tidak ada log" : "No logs"}</div>
                  <div className="text-xs mt-1 opacity-70">
                    {data?.source?.startsWith("db") ? (lang === "id" ? "Fallback dari database" : "Fallback from database") : (lang === "id" ? "Container mungkin belum menulis log" : "Container may not have written logs yet")}
                  </div>
                </div>
              ) : (
                <div className="divide-y divide-white/[0.06]">
                  {data.logs.map((l, i) => (
                    <div key={i} className={`flex gap-3 px-4 py-1.5 ${lineBg(l.level)} hover:bg-white/[0.04] transition-colors group`}>
                      <span className="shrink-0 select-none text-white/30 text-[11px] w-8 text-right">{l.idx + 1}</span>
                      <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase leading-4 tracking-wide border ${l.level === "error" ? "bg-red-500/15 text-red-400 border-red-500/20" : l.level === "warn" ? "bg-amber-500/15 text-amber-400 border-amber-500/20" : l.level === "debug" ? "bg-zinc-700/50 text-zinc-400 border-white/10" : "bg-blue-500/10 text-blue-400 border-blue-500/20"}`}>
                        {l.level}
                      </span>
                      <span className={`flex-1 break-all whitespace-pre-wrap ${lineColor(l.level)}`}>{l.line}</span>
                    </div>
                  ))}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>
          )}

          {/* Footer meta */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-t bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1"><ShieldCheck className="h-3 w-3" /> admin only · max 500 lines</span>
              {data && <span>source: {data.source}</span>}
            </div>
            <div className="flex items-center gap-2">
              {auto && <span className="inline-flex items-center gap-1"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />{lang === "id" ? "live (5s)" : "live (5s)"}</span>}
              <span>{data ? `${data.lines_returned}/${data.lines_requested}` : ""}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Hint */}
      <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
        {lang === "id"
          ? "Tips: pilih tab bot untuk error generate, api untuk aktivitas admin, postgres untuk query lambat, web untuk request dashboard. Jika di VPS docker, backend pakai docker logs --tail. Jika di lokal tanpa docker, fallback otomatis ke tabel generations / admin_audit."
          : "Tips: bot tab = generation errors, api = admin actions, postgres = slow queries, web = dashboard requests. On VPS docker, backend uses docker logs --tail. Without docker, auto-fallback to generations / admin_audit tables."}
      </div>
    </div>
  );
}
