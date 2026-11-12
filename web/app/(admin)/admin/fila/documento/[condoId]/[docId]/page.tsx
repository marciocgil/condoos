import Link from "next/link";

import { RelationsList, type Relations } from "@/components/condoos/RelationsList";
import { ReviewForm } from "@/components/ReviewForm";
import { apiGet } from "@/lib/api";
import type { Review } from "@/lib/types";

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ condoId: string; docId: string }>;
}) {
  const { condoId, docId } = await params;
  const [review, relations] = await Promise.all([
    apiGet<Review>(`/condominiums/${condoId}/documents/${docId}/review`),
    apiGet<Relations>(`/condominiums/${condoId}/relations/document/${docId}`),
  ]);
  const isPdf = review.mime_type === "application/pdf";
  const isImage = review.mime_type.startsWith("image/");

  return (
    <>
      <Link href="/admin/fila" className="text-sm text-fg-2">
        ‹ Fila de exceções
      </Link>
      <h1 className="mt-1 text-xl font-semibold break-all">{review.original_filename}</h1>
      {review.reasons.length > 0 && (
        <ul
          className="mt-3 space-y-1 rounded-[var(--radius-card)] border border-warning/60 bg-warning/10 p-4 text-sm"
          aria-label="Motivos da revisão"
        >
          {review.reasons.map((r) => (
            <li key={r}>• {r}</li>
          ))}
        </ul>
      )}
      <div className="mt-4 grid grid-cols-2 gap-6">
        <section
          aria-label="Documento"
          className="h-[78vh] overflow-hidden rounded-[var(--radius-card)] border border-control bg-surface"
        >
          {isPdf && <iframe title="Documento" src={review.file_url} className="h-full w-full" />}
          {isImage && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={review.file_url}
              alt="Documento enviado"
              className="h-full w-full object-contain"
            />
          )}
          {!isPdf && !isImage && (
            <pre className="h-full overflow-auto p-4 text-xs whitespace-pre-wrap">
              {review.text_content ?? "Pré-visualização indisponível. "}
              <a href={review.file_url} className="text-accent underline">
                Abrir arquivo
              </a>
            </pre>
          )}
        </section>
        <section aria-label="Campos extraídos" className="h-[78vh] overflow-auto">
          <ReviewForm review={review} />
        </section>
      </div>
      <div className="mt-6 max-w-3xl">
        <RelationsList data={relations} title="Relações do documento" />
      </div>
    </>
  );
}
