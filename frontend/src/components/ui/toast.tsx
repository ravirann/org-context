import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { create } from "zustand";

import { cn } from "@/lib/utils";

/**
 * Toast system.
 *
 *   const { toast } = useToast();
 *   toast({ title: "Saved", variant: "success" });
 *   toast({ title: "Failed", description: err.detail, variant: "error" });
 *
 * <Toaster /> is mounted once in App.tsx. Toasts auto-dismiss after 5s.
 */

export type ToastVariant = "success" | "error" | "info";

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  /** ms before auto-dismiss; 0 disables. Default 5000. */
  duration?: number;
}

export interface ToastItem extends Required<Pick<ToastOptions, "title" | "variant">> {
  id: string;
  description?: string;
}

interface ToastState {
  toasts: ToastItem[];
  toast: (options: ToastOptions) => string;
  dismiss: (id: string) => void;
}

let counter = 0;
const timers = new Map<string, ReturnType<typeof setTimeout>>();

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  toast: ({ title, description, variant = "info", duration = 5000 }) => {
    const id = `toast-${++counter}`;
    set((state) => ({
      toasts: [...state.toasts, { id, title, description, variant }],
    }));
    if (duration > 0) {
      timers.set(
        id,
        setTimeout(() => get().dismiss(id), duration),
      );
    }
    return id;
  },
  dismiss: (id) => {
    const timer = timers.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.delete(id);
    }
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
}));

export function useToast() {
  const toast = useToastStore((s) => s.toast);
  const dismiss = useToastStore((s) => s.dismiss);
  return { toast, dismiss };
}

const VARIANT_ICON = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
} as const;

const VARIANT_CLASSES: Record<ToastVariant, string> = {
  success: "border-emerald-500/40 [&>svg]:text-emerald-500",
  error: "border-destructive/50 [&>svg]:text-destructive",
  info: "border-border [&>svg]:text-primary",
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <div
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-4 right-4 z-100 flex w-80 flex-col gap-2"
    >
      {toasts.map((item) => {
        const Icon = VARIANT_ICON[item.variant];
        return (
          <div
            key={item.id}
            role={item.variant === "error" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex items-start gap-2.5 rounded-lg border bg-card p-3 text-card-foreground shadow-lg",
              VARIANT_CLASSES[item.variant],
            )}
          >
            <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium leading-tight">{item.title}</p>
              {item.description ? (
                <p className="mt-0.5 break-words text-xs text-muted-foreground">
                  {item.description}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              aria-label="Dismiss notification"
              className="shrink-0 rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => dismiss(item.id)}
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
