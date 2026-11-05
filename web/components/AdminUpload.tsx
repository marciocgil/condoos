"use client";

import { useState } from "react";

import { UploadForm } from "@/components/UploadForm";

interface Condo {
  id: string;
  name: string;
  slug: string;
}

export function AdminUpload({ condos }: { condos: Condo[] }) {
  const [selected, setSelected] = useState(condos[0]?.id ?? "");
  if (condos.length === 0) return <p>Seu papel não permite enviar documentos.</p>;
  const current = condos.find((c) => c.id === selected);
  return (
    <div className="space-y-4">
      <label className="block">
        <span className="text-sm font-medium">Condomínio</span>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2"
        >
          {condos.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {current && (
        <p className="text-xs text-gray-500">
          E-mail de entrada: <code>{current.slug}@ingest.condoos.local</code>
        </p>
      )}
      <UploadForm key={selected} condominiumId={selected} />
    </div>
  );
}
