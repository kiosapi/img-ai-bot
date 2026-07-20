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
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full sm:max-w-md max-h-[92vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border bg-card p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold">{title}</h3>
          <button onClick={onClose} className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mb-3 block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
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
        <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 max-h-56 overflow-auto rounded-md border bg-popover p-1 shadow-xl">
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
                  "flex w-full items-center justify-between rounded-sm px-2.5 py-2.5 text-sm text-left transition-colors",
                  active ? "bg-primary text-primary-foreground" : "hover:bg-accent hover:text-accent-foreground"
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
        className="flex h-10 w-full items-center justify-between rounded-md border bg-card px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring hover:border-foreground/20 disabled:opacity-50">
        <span className={cn("truncate", !selected && "text-muted-foreground")}>{selected ? selected.label : placeholder}</span>
        <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute z-50 mt-1.5 w-full rounded-md border bg-popover p-1 shadow-xl max-h-56 overflow-auto">
          {options.map(o => (
            <button key={o.value} type="button" onClick={()=>{setOpen(false); onChange(o.value);}}
              className={cn("flex w-full items-center justify-between rounded-sm px-3 py-2.5 text-sm text-left hover:bg-accent", o.value===value && "bg-primary text-primary-foreground")}>
              <span>{o.label}</span>{o.value===value && <Check className="h-4 w-4" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
