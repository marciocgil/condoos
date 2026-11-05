"use client";

import { useState } from "react";

import { Field, controlClass } from "@/components/ui/Field";
import { UploadForm } from "@/components/UploadForm";

interface Condo {
  id: string;
  name: string;
  slug: string;
}

export function AdminUpload({ condos }: { condos: Condo[] }) {
  const [selected, setSelected] = useState(condos[0]?.id ?? "");
  if (condos.length === 0)
    return <p className="text-fg-2">Seu papel não permite enviar documentos.</p>;
  const current = condos.find((c) => c.id === selected);
  return (
    <div className="space-y-4">
      <Field
        id="condo-select"
        label="Condomínio"
        hint={current ? `E-mail de entrada: ${current.slug}@ingest.condoos.local` : undefined}
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
