"use client";

import { useState, type FormEvent } from "react";

type State = "idle" | "sending" | "sent" | "error";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>("idle");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("sending");
    try {
      const res = await fetch("/api/auth/magic-link", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setState(res.ok ? "sent" : "error");
    } catch {
      setState("error");
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6">
      <p className="text-sm font-semibold tracking-wide text-brand-600">CondoOS</p>
      <h1 className="mt-1 text-2xl font-semibold">Entrar</h1>
      <p className="mt-2 text-sm text-gray-600">
        Digite seu e-mail. Enviaremos um link de acesso que vale por 15 minutos.
      </p>

      {state === "sent" ? (
        <div role="status" className="mt-6 rounded-lg bg-brand-50 p-4 text-sm text-brand-900">
          Se o e-mail estiver cadastrado, você receberá o link em instantes. Confira também a caixa
          de spam.
        </div>
      ) : (
        <form onSubmit={onSubmit} className="mt-6 space-y-3">
          <label htmlFor="email" className="block text-sm font-medium">
            E-mail
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            inputMode="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-3 text-base outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
          />
          <button
            type="submit"
            disabled={state === "sending"}
            className="w-full rounded-lg bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {state === "sending" ? "Enviando…" : "Receber link de acesso"}
          </button>
          {state === "error" && (
            <p role="alert" className="text-sm text-red-700">
              Não foi possível enviar agora. Tente de novo em alguns minutos.
            </p>
          )}
        </form>
      )}
    </main>
  );
}
