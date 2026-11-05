import type { ReactNode } from "react";

export interface TimelineItem {
  id: string;
  when: string;
  who: string;
  what: ReactNode;
  detail?: ReactNode;
  icon?: ReactNode;
}

/** Activity Timeline (DS §5.10): date/time, author, description. */
export function Timeline({ items, label }: { items: TimelineItem[]; label: string }) {
  return (
    <ol aria-label={label} className="relative space-y-4 border-l border-line pl-5">
      {items.map((item) => (
        <li key={item.id} className="relative">
          <span
            aria-hidden
            className="absolute top-1 -left-[27px] flex h-3.5 w-3.5 items-center justify-center rounded-full border border-control bg-bg text-fg-2"
          >
            {item.icon}
          </span>
          <p className="text-sm">
            <span className="font-medium">{item.who}</span> {item.what}
          </p>
          <p className="text-xs text-muted">{item.when}</p>
          {item.detail && <div className="mt-1 text-[13px] text-fg-2">{item.detail}</div>}
        </li>
      ))}
    </ol>
  );
}
