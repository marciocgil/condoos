import Link from "next/link";
import type { ReactNode } from "react";

import { cx } from "./cx";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  className?: string;
}

/** Compact, readable table (DS §5.8) with semantic headers and an empty state. */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  rowHref,
  caption,
  empty,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  rowHref?: (row: T) => string;
  caption?: string;
  empty?: ReactNode;
}) {
  if (rows.length === 0 && empty) return <>{empty}</>;
  return (
    <div className="overflow-x-auto rounded-[var(--radius-card)] border border-line bg-surface">
      <table className="w-full text-left text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="border-b border-line text-[12px] text-fg-2">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={cx(
                  "px-4 py-3 font-medium",
                  c.align === "right" && "text-right",
                  c.className,
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row) => (
            <tr key={rowKey(row)} className="transition-ui hover:bg-elevated/60">
              {columns.map((c, i) => {
                const content = c.cell(row);
                return (
                  <td
                    key={c.key}
                    className={cx("px-4 py-3", c.align === "right" && "text-right", c.className)}
                  >
                    {i === 0 && rowHref ? (
                      <Link href={rowHref(row)} className="font-medium hover:text-accent">
                        {content}
                      </Link>
                    ) : (
                      content
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
