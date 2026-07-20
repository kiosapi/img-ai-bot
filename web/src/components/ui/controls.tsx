import * as React from "react";
import { cn } from "@/lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border bg-card px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-24 w-full rounded-md border bg-card px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";

function Badge({ className, variant = "default", ...props }: React.HTMLAttributes<HTMLSpanElement> & { variant?: "default" | "success" | "destructive" | "muted" }) {
  const variants = {
    default: "bg-primary/15 text-primary",
    success: "bg-success/15 text-success",
    destructive: "bg-destructive/15 text-destructive",
    muted: "bg-muted text-muted-foreground",
  };
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold", variants[variant], className)} {...props} />;
}

function Switch({ checked, onChange, onCheckedChange }: { checked: boolean; onChange?: (v: boolean) => void; onCheckedChange?: (v: boolean) => void }) {
  const handleChange = (v: boolean) => { if (onCheckedChange) onCheckedChange(v); if (onChange) onChange(v); };
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => handleChange(!checked)}
      className={cn("relative inline-flex h-7 w-12 shrink-0 cursor-pointer rounded-full transition-colors", checked ? "bg-success" : "bg-input")}
    >
      <span className={cn("pointer-events-none absolute top-0.5 left-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform", checked && "translate-x-5")} />
    </button>
  );
}

export { Input, Textarea, Badge, Switch };
