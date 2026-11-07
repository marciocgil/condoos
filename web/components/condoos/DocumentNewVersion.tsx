"use client";

import { FileUp } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { controlClass, Field } from "@/components/ui/Field";

/** Send a new file of the same document (CB-031): the previous one is kept, leaves the
 * search, and the contract starts pointing to the new one. */
export function DocumentNewVersion({
  condominiumId,
  documentId,
  label = "Enviar nova versão do contrato",
}: {
  condominiumId: string;
  documentId: string;
  label?: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function upload() {
    if (!file) return;
    setBusy(true);
    setMessage(null);
    const data = new FormData();
    data.append("file", file);
    const res = await fetch(`/api/condominiums/${condominiumId}/documents/${documentId}/versions`, {
      method: "POST",
      body: data,
    });
    const body = (await res.json().catch(() => null)) as {
      detail?: unknown;
      version?: number;
    } | null;
    setBusy(false);
    if (!res.ok) {
      setMessage({
        ok: false,
        text: typeof body?.detail === "string" ? body.detail : "Não foi possível enviar agora.",
      });
      return;
    }
    setOpen(false);
    setMessage({
      ok: true,
      text: `Versão ${body?.version ?? ""} recebida. A anterior fica guardada; a leitura da nova começa em instantes.`,
    });
    router.refresh();
  }

  return (
    <div className="space-y-2">
      {!open ? (
        <Button
          variant="secondary"
          size="sm"
          icon={<FileUp size={14} />}
          onClick={() => setOpen(true)}
        >
          {label}
        </Button>
      ) : (
        <div className="space-y-3 rounded-[var(--radius-card)] border border-line bg-bg-2 p-3">
          <Field id="nv-file" label="Arquivo da nova versão" required>
            <input
              id="nv-file"
              type="file"
              className={controlClass}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              disabled={busy || !file}
              onClick={() => void upload()}
            >
              Enviar versão
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
          </div>
        </div>
      )}
      {message && (
        <p
          role={message.ok ? "status" : "alert"}
          className={message.ok ? "text-sm text-success" : "text-sm text-danger"}
        >
          {message.text}
        </p>
      )}
    </div>
  );
}
