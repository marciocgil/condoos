"use client";

import { FileUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ChangeEvent } from "react";

import { FirstValueCard } from "@/components/condoos/FirstValueCard";
import { buttonClass } from "@/components/ui/Button";
import { send } from "@/lib/client";
import type { FirstValue, UploadResult } from "@/lib/types";

const POLL_MS = 2000;
const MAX_POLLS = 90; // three minutes: then the person is told it is still being read

/** Upload with feedback (LB-007, F01): sends one file, follows its reading and opens the
 * first-value card. A file already received opens the existing document's card. */
export function FirstContractUpload({
  condominiumId,
  primary = true,
  onSent,
}: {
  condominiumId: string;
  primary?: boolean;
  onSent?: () => void;
}) {
  const router = useRouter();
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [card, setCard] = useState<FirstValue | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!documentId) return;
    let stop = false;
    let polls = 0;
    async function poll() {
      if (stop) return;
      polls += 1;
      try {
        const res = await fetch(
          `/api/condominiums/${condominiumId}/launch/first-value/${documentId}`,
        );
        if (res.ok) {
          const data = (await res.json()) as FirstValue;
          setCard(data);
          if (data.status !== "lendo") {
            await send(
              "POST",
              `/condominiums/${condominiumId}/launch/first-value/${documentId}/shown`,
            );
            router.refresh();
            return;
          }
        }
      } catch {
        // a network blip: try again on the next tick
      }
      if (polls >= MAX_POLLS) {
        setNotice("A leitura está demorando. Pode sair desta tela: o resultado fica guardado.");
        return;
      }
      setTimeout(() => void poll(), POLL_MS);
    }
    void poll();
    return () => {
      stop = true;
    };
  }, [condominiumId, documentId, router]);

  async function upload(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setBusy(true);
    setNotice(null);
    setCard(null);
    const form = new FormData();
    form.append("files", file);
    try {
      const res = await fetch(`/api/condominiums/${condominiumId}/documents`, {
        method: "POST",
        body: form,
      });
      const [result] = res.ok ? ((await res.json()) as UploadResult[]) : [];
      if (!result) setNotice("Não foi possível enviar. Tente de novo.");
      else if (result.error || !result.document_id) setNotice(result.error ?? "Arquivo inválido.");
      else {
        if (result.duplicate) setNotice("Este arquivo já tinha chegado. Mostro a leitura dele.");
        setDocumentId(result.document_id);
        onSent?.();
      }
    } catch {
      setNotice("Sem conexão. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <label className={`${buttonClass(primary ? "primary" : "secondary")} w-full cursor-pointer`}>
        <FileUp size={16} aria-hidden />
        {busy ? "Enviando…" : "Enviar o contrato"}
        <input
          type="file"
          accept=".pdf,image/jpeg,image/png,image/webp"
          className="sr-only"
          aria-label="Escolher o arquivo do contrato"
          disabled={busy}
          onChange={(e: ChangeEvent<HTMLInputElement>) => void upload(e.target.files)}
        />
      </label>
      {notice && (
        <p role="status" className="text-sm text-fg-2">
          {notice}
        </p>
      )}
      {card && <FirstValueCard card={card} />}
    </div>
  );
}
