import type { ReactNode } from "react";

/** Empty state (DS §8): what is happening and the next step. */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-[var(--radius-card)] border border-dashed border-line bg-bg-2 px-6 py-10 text-center">
      {icon && (
        <div className="mx-auto mb-3 flex justify-center text-muted" aria-hidden>
          {icon}
        </div>
      )}
      <p className="font-medium">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-md text-[13px] text-fg-2">{children}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}
