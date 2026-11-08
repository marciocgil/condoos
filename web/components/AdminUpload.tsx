"use client";

import { useState } from "react";

import { Field, controlClass } from "@/components/ui/Field";
import { UploadForm } from "@/components/UploadForm";

interface Condo {
  id: string;
  name: string;
  slug: string;
}

export function AdminUpload({ condos, initial }: { condos: Condo[]; initial?: string }) {
  const [selected, setSelected] = useState(
    condos.some((c) => c.id === initial) ? initial! : (condos[0]?.id ?? ""),
  );
  if (condos.length === 0)
    return <p className="text-fg-2">Seu papel não permite enviar documentos.</p>;
  const current = condos.find((c) => c.id === selected);
  return (
    <div className="space-y-4">
      <Field
        id="condo-select"
        label="Condomínio"
        hint={current ? "O e-mail de entrada do condomínio está em Configurações." : undefined}
      >
        <select
          id="condo-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className={controlClass}
        >
          {condos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>
      <UploadForm key={selected} condominiumId={selected} />
    </div>
  );
}
