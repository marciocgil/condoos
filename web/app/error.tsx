"use client";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6">
      <h1 className="text-xl font-semibold">Algo deu errado</h1>
      <p className="mt-2 text-sm text-gray-600">Não foi possível carregar esta tela agora.</p>
      <button type="button" onClick={reset} className="mt-4 font-medium text-brand-600 underline">
        Tentar de novo
      </button>
    </main>
  );
}
