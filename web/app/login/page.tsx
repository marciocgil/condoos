"use client";

import { useState, type FormEvent } from "react";

import { Logo } from "@/components/layout/Logo";
import { buttonClass } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/Field";

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
      <Logo />
      <h1 className="mt-6 text-2xl font-semibold">Entrar</h1>
      <p className="mt-2 text-sm text-fg-2">
        Digite seu e-mail. Enviaremos um link de acesso que vale por 15 minutos.
      </p>

      {state === "sent" ? (
        <div
          role="status"
          className="mt-6 rounded-[var(--radius-control)] bg-accent/10 p-4 text-sm text-fg"
        >
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
            className={`${controlClass} h-11 text-base`}
          />
          <button
            type="submit"
            disabled={state === "sending"}
            className={`${buttonClass("primary")} h-11 w-full`}
          >
            {state === "sending" ? "Enviando…" : "Receber link de acesso"}
          </button>
          {state === "error" && (
            <p role="alert" className="text-sm text-danger">
              Não foi possível enviar agora. Tente de novo em alguns minutos.
            </p>
          )}
        </form>
      )}
    </main>
  );
}
