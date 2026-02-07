"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

export type ToastVariant = "success" | "error" | "info";

type ToastProps = {
  message: string;
  variant?: ToastVariant;
  duration?: number;
  onDismiss: () => void;
};

const variantStyles: Record<ToastVariant, { bg: string; border: string; text: string }> = {
  success: {
    bg: "rgba(34, 197, 94, 0.12)",
    border: "rgba(34, 197, 94, 0.3)",
    text: "rgba(34, 197, 94, 1)",
  },
  error: {
    bg: "rgba(220, 38, 38, 0.12)",
    border: "rgba(220, 38, 38, 0.3)",
    text: "rgba(248, 113, 113, 1)",
  },
  info: {
    bg: "rgba(99, 102, 241, 0.12)",
    border: "rgba(99, 102, 241, 0.3)",
    text: "rgba(165, 180, 252, 1)",
  },
};

export function Toast({ message, variant = "info", duration = 5000, onDismiss }: ToastProps) {
  const [isVisible, setIsVisible] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    timerRef.current = setTimeout(() => {
      setIsVisible(false);
      setTimeout(onDismiss, 200);
    }, duration);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [duration, onDismiss]);

  const style = variantStyles[variant];

  return (
    <div
      className="mb-4 flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm font-medium transition-all duration-200"
      style={{
        backgroundColor: style.bg,
        borderColor: style.border,
        color: style.text,
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? "translateY(0)" : "translateY(-8px)",
      }}
      role="alert"
    >
      <span>{message}</span>
      <button
        type="button"
        onClick={() => {
          setIsVisible(false);
          setTimeout(onDismiss, 200);
        }}
        className="flex-shrink-0 rounded-lg p-1 transition-colors hover:bg-white/10"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

type ToastItem = {
  id: number;
  message: string;
  variant: ToastVariant;
};

let nextId = 0;

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  function showToast(message: string, variant: ToastVariant = "info") {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, variant }]);
  }

  function dismissToast(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  function ToastContainer() {
    if (toasts.length === 0) return null;
    return (
      <div className="space-y-2">
        {toasts.map((t) => (
          <Toast
            key={t.id}
            message={t.message}
            variant={t.variant}
            onDismiss={() => dismissToast(t.id)}
          />
        ))}
      </div>
    );
  }

  return { showToast, ToastContainer };
}
