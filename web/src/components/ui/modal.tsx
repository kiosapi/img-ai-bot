"use client";
import * as React from "react";
import { X, ChevronDown, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export function Modal({ open, onClose, title, children }: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode;
}) {
  React.useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", h); document.body.style.overflow = ""; };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-[91] w-full sm:max-w-lg max-h-[90vh] sm:max-h-[92vh] flex flex-col rounded-t-2xl sm:rounded-2xl border bg-card shadow-2xl overflow-hidden">
        <div className="flex shrink-0 items-center justify-between border-b px-5 py-4">
          <h3 className="text-[15px] font-bold leading-none">{title}</h3>
          <button onClick={onClose} className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto overscroll-contain p-5">
          {children}
        </div>
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mb-3 block">
      <span className="mb-1.5 block text-[13px] font-semibold tracking-tight">{label}</span>
      {children}
    </label>
  );
}

type Option = { value: string; label: string };

function parseChildrenToOptions(children: React.ReactNode): Option[] {
  const opts: Option[] = [];
  React.Children.forEach(children, (child: any) => {
    if (!React.isValidElement(child)) return;
    const p = child.props as any;
    const v = p?.value ?? "";
    let label: string = "";
    const ch = p?.children;
    if (typeof ch === "string") label = ch;
    else if (Array.isArray(ch)) label = ch.join("");
    else label = String(ch ?? v);
    opts.push({ value: String(v), label });
  });
  return opts;
}

export function Select({ value, onChange, children, className, placeholder = "Pilih...", disabled }: {
  value?: string;
  onChange?: (e: any) => void;
  children?: React.ReactNode;
  className?: string;
  placeholder?: string;
  disabled?: boolean;
  id?: string; name?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const options = React.useMemo(() => parseChildrenToOptions(children), [children]);
  const selected = options.find(o => o.value === value);

  React.useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const handleSelect = (v: string) => {
    setOpen(false);
    if (onChange) {
      try { onChange({ target: { value: v } }); } catch { (onChange as any)(v); }
    }
  };

  return (
    <div ref={ref} className={cn("relative", className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen(o => !o)}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md border bg-card px-3 py-2 text-sm outline-none transition-all",
          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          "hover:border-foreground/20"
        )}
      >
        <span className={cn("truncate text-left", !selected && "text-muted-foreground")}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-[100] max-h-56 overflow-auto rounded-xl border bg-card p-1 shadow-[0_12px_40px_rgba(0,0,0,0.35)] backdrop-blur-none">
          {options.length === 0 ? (
            <div className="px-3 py-2 text-xs text-muted-foreground">Tidak ada opsi</div>
          ) : options.map(opt => {
            const active = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleSelect(opt.value)}
                className={cn(
                  "flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-[13px] text-left transition-colors",
                  active ? "bg-primary text-primary-foreground font-semibold" : "hover:bg-muted hover:text-foreground text-foreground"
                )}
              >
                <span className="truncate">{opt.label}</span>
                {active && <Check className="h-4 w-4 shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function CustomSelect({ value, onChange, options, placeholder = "Pilih...", className, disabled }: {
  value?: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const selected = options.find(o => o.value === value);
  React.useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);
  return (
    <div ref={ref} className={cn("relative", className)}>
      <button type="button" disabled={disabled} onClick={() => !disabled && setOpen(o=>!o)}
        className="flex h-10 w-full items-center justify-between rounded-xl border bg-card px-3 py-2 text-[13px] font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring hover:border-foreground/20 disabled:opacity-50 shadow-sm">
        <span className={cn("truncate text-left", !selected && "text-muted-foreground font-normal")}>{selected ? selected.label : placeholder}</span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute z-[100] mt-2 w-full rounded-xl border bg-card p-1 shadow-[0_12px_40px_rgba(0,0,0,0.35)] max-h-56 overflow-auto">
          {options.map(o => (
            <button key={o.value} type="button" onClick={()=>{setOpen(false); onChange(o.value);}}
              className={cn("flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-[13px] text-left transition-colors", o.value===value ? "bg-primary text-primary-foreground font-semibold" : "hover:bg-muted text-foreground")}>
              <span className="truncate">{o.label}</span>{o.value===value && <Check className="h-4 w-4 shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
