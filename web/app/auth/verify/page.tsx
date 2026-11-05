"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

function Verify() {
  const params = useSearchParams();
  const router = useRouter();
  const [failed, setFailed] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    // The token is consumed with a POST from the page (not on GET), so e-mail link scanners
    // that only fetch the URL cannot burn it.
    if (started.current) return;
    started.current = true;
    const token = params.get("token");
    if (!token) {
      setFailed(true);
      return;
    }
    fetch("/api/auth/verify", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then((res) => (res.ok ? router.replace("/") : setFailed(true)))
      .catch(() => setFailed(true));
  }, [params, router]);

  if (failed) {
    return (
      <div role="alert">
        <h1 className="text-xl font-semibold">Link inválido ou expirado</h1>
        <p className="mt-2 text-sm text-fg-2">Cada link vale por 15 minutos e um único uso.</p>
        <Link href="/login" className="mt-4 inline-block font-medium text-accent underline">
          Pedir um novo link
        </Link>
      </div>
    );
  }
  return <p className="text-fg-2">Validando seu acesso…</p>;
}

export default function VerifyPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6">
      <Suspense fallback={<p className="text-fg-2">Validando seu acesso…</p>}>
        <Verify />
      </Suspense>
    </main>
  );
}
