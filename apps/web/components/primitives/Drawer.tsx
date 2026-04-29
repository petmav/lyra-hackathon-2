"use client";

import { useEffect } from "react";
import { cn } from "@/lib/utils/cn";
import { X } from "lucide-react";

/**
 * Right-edge slide-in drawer used for step details, finding details, etc.
 * Closes on Escape and when the backdrop is clicked.
 *
 * No fancy spring animation — just the same crisp linear cubic-bezier
 * easing the page-enter uses, applied as a CSS transition on translate.
 */
export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = "wide"
}: {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  children?: React.ReactNode;
  width?: "narrow" | "wide" | "xl";
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const widthClass =
    width === "narrow" ? "w-[420px]" : width === "xl" ? "w-[780px]" : "w-[560px]";

  return (
    <>
      <div
        aria-hidden={!open}
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-black/50 transition-opacity",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
      />
      <aside
        role="dialog"
        aria-modal
        className={cn(
          "fixed right-0 top-0 z-50 h-full max-w-[100vw] bg-ink-2 border-l border-rule",
          "transition-transform duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)]",
          widthClass,
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-rule bg-ink-2 px-6 py-4">
          <div className="min-w-0">
            {subtitle && <div className="smallcaps mb-1">{subtitle}</div>}
            {title && <div className="ed-h2 text-paper truncate">{title}</div>}
          </div>
          <button
            onClick={onClose}
            className="text-paper-dim hover:text-paper -mr-1 -mt-1 p-1"
            aria-label="Close"
          >
            <X size={18} strokeWidth={1.5} />
          </button>
        </header>
        <div className="overflow-y-auto h-[calc(100%-65px)]">{children}</div>
      </aside>
    </>
  );
}
