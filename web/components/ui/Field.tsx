import type { ReactNode } from "react";

import { cx } from "./cx";

export const controlClass =
  "transition-ui h-10 w-full rounded-[var(--radius-control)] border border-control bg-bg-2 px-3 text-sm text-fg placeholder:text-muted hover:border-fg-2 aria-[invalid=true]:border-danger";
export const textareaClass = cx(controlClass, "h-auto min-h-20 py-2");

/** Label + control + hint/error, with the error announced to screen readers. */
export function Field({
  id,
  label,
  required,
  hint,
  error,
  aside,
  children,
}: {
  id: string;
  label: ReactNode;
  required?: boolean;
  hint?: ReactNode;
  error?: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 flex items-baseline justify-between gap-2 text-[13px] font-medium"
      >
        <span>
          {label}
          {required && (
            <span className="text-danger" aria-hidden>
              {" "}
              *
            </span>
          )}
        </span>
        {aside}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-muted">{hint}</p>}
      {error && (
        <p className="mt-1 text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
