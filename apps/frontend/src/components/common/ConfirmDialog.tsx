"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "danger";
  /** If set, user must type this exact string to enable the confirm button */
  requiredConfirmText?: string;
  isPending?: boolean;
  onConfirm: () => void;
};

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  requiredConfirmText,
  isPending = false,
  onConfirm,
}: ConfirmDialogProps) {
  const [inputValue, setInputValue] = useState("");

  const isConfirmEnabled = requiredConfirmText
    ? inputValue === requiredConfirmText && !isPending
    : !isPending;

  const confirmBg =
    variant === "danger"
      ? "rgba(220, 38, 38, 0.8)"
      : "rgba(99, 102, 241, 0.7)";
  const confirmBorder =
    variant === "danger"
      ? "rgba(220, 38, 38, 0.5)"
      : "rgba(99, 102, 241, 0.5)";

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setInputValue("");
        onOpenChange(next);
      }}
    >
      <DialogContent
        className="sm:max-w-md"
        style={{ backgroundColor: "rgba(24, 24, 27, 0.98)", borderColor: "rgba(255,255,255,0.08)" }}
      >
        <DialogHeader>
          <DialogTitle style={{ color: "rgba(230, 233, 242, 0.95)" }}>{title}</DialogTitle>
          <DialogDescription style={{ color: "rgba(138, 144, 178, 1)" }}>
            {description}
          </DialogDescription>
        </DialogHeader>

        {requiredConfirmText && (
          <div className="mt-2">
            <label className="text-xs font-medium" style={{ color: "rgba(138,144,178,1)" }}>
              Type <span className="font-bold" style={{ color: "rgba(248, 113, 113, 1)" }}>{requiredConfirmText}</span> to confirm
            </label>
            <input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="mt-2 w-full rounded-xl border bg-transparent px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-[rgba(138,92,255,0.4)] focus:border-[rgba(138,92,255,0.4)]"
              style={{ borderColor: "rgba(255,255,255,0.10)", color: "rgba(230,233,242,0.95)" }}
              placeholder={requiredConfirmText}
              autoFocus
            />
          </div>
        )}

        <DialogFooter className="mt-4">
          <button
            type="button"
            onClick={() => {
              setInputValue("");
              onOpenChange(false);
            }}
            className="btn-press rounded-xl border px-4 py-2 text-sm font-medium transition-colors hover:bg-white/5"
            style={{ borderColor: "rgba(255,255,255,0.10)", color: "rgba(230,233,242,0.95)" }}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={() => {
              onConfirm();
              setInputValue("");
            }}
            disabled={!isConfirmEnabled}
            className="btn-press btn-glow rounded-xl border px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-40"
            style={{
              backgroundColor: confirmBg,
              borderColor: confirmBorder,
              color: "rgba(255, 255, 255, 0.95)",
            }}
          >
            {isPending ? "Processing..." : confirmLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
