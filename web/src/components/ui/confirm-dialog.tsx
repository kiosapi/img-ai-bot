"use client";
import * as React from "react";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Modal } from "./modal";
import { Button } from "./button";

/**
 * Reusable confirmation dialog to replace the browser's native confirm().
 * Styled consistently with the rest of the dashboard (dark/light aware).
 */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = "Konfirmasi",
  description,
  confirmLabel = "Ya, lanjutkan",
  cancelLabel = "Batal",
  variant = "default",
  loading = false,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  description: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "destructive" | "success";
  loading?: boolean;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div className="mb-5 flex items-start gap-3">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
            variant === "destructive"
              ? "bg-destructive/15 text-destructive"
              : variant === "success"
              ? "bg-success/15 text-success"
              : "bg-primary/15 text-primary"
          )}
        >
          <AlertTriangle className="h-5 w-5" />
        </div>
        <div className="pt-1.5 text-sm text-muted-foreground">{description}</div>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" className="flex-1" onClick={onClose} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button
          variant={variant === "default" ? "default" : variant}
          className="flex-1"
          onClick={onConfirm}
          disabled={loading}
        >
          {loading ? "..." : confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
