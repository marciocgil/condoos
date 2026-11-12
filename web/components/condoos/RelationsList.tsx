import Link from "next/link";

import { Card, CardTitle } from "@/components/ui/Card";

export type Relations = {
  object: { kind: string; id: string; label: string };
  groups: {
    title: string;
    items: {
      kind: string;
      id: string;
      label: string;
      relation: string;
      href: string | null;
    }[];
  }[];
};

/** What a document, contract or supplier is linked to (FR-014, D126), from the links the
 * product already keeps. Nothing here is inferred. */
export function RelationsList({ data, title = "Relações" }: { data: Relations; title?: string }) {
  return (
    <Card data-testid="relations">
      <CardTitle>{title}</CardTitle>
      {data.groups.length === 0 ? (
        <p className="mt-2 text-sm text-fg-2">Nenhum vínculo registrado ainda.</p>
      ) : (
        <div className="mt-2 space-y-4">
          {data.groups.map((g) => (
            <section key={g.title} aria-label={g.title}>
              <h3 className="text-xs font-semibold tracking-wide text-fg-2 uppercase">
                {g.title} ({g.items.length})
              </h3>
              <ul className="mt-1 space-y-1 text-[13px]">
                {g.items.map((i) => (
                  <li key={`${i.kind}-${i.id}-${i.relation}`}>
                    {i.href ? (
                      <Link href={i.href} className="underline-offset-2 hover:underline">
                        {i.label}
                      </Link>
                    ) : (
                      i.label
                    )}
                    <span className="text-fg-2"> · {i.relation}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </Card>
  );
}
