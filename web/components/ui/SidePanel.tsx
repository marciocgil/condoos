"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

/**
 * Side Detail Panel (DS §5.7) on the native <dialog>: focus is trapped and restored, Esc
 * closes, the page behind keeps its context.
 */
export function SidePanel({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-label={title}
      className="m-0 ml-auto h-dvh max-h-dvh w-full max-w-[480px] border-l border-line bg-bg-2 p-0 text-fg"
    >
      <div className="flex h-full flex-col">
        <header className="flex h-16 items-center justify-between border-b border-line px-6">
          <h2 className="text-base font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius-control)] p-2 text-fg-2 hover:bg-surface hover:text-fg"
            aria-label="Fechar painel"
          >
            <X size={18} />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <footer className="border-t border-line px-6 py-4">{footer}</footer>}
      </div>
    </dialog>
  );
}
