"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { textareaClass } from "@/components/ui/Field";

export function CommentForm({
  condominiumId,
  findingId,
}: {
  condominiumId: string;
  findingId: string;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function send() {
    const res = await fetch(`/api/condominiums/${condominiumId}/findings/${findingId}/comments`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ body }),
    });
    if (res.ok) {
      setBody("");
      setError(null);
      router.refresh();
    } else {
      setError("Não foi possível enviar o comentário.");
    }
  }
  return (
    <div className="space-y-2">
      <label htmlFor="comment" className="text-[13px] font-medium">
        Comentário
      </label>
      <textarea
        id="comment"
        rows={2}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        className={textareaClass}
      />
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <Button size="sm" disabled={body.trim().length < 2} onClick={send}>
        Comentar
      </Button>
    </div>
  );
}
