import Link from "next/link";

import { Logo } from "@/components/layout/Logo";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6">
      <Logo />
      <h1 className="mt-1 text-xl font-semibold">Página não encontrada</h1>
      <p className="mt-2 text-sm text-fg-2">O endereço não existe ou você não tem acesso a ele.</p>
      <Link href="/" className="mt-4 font-medium text-accent underline">
        Voltar ao início
      </Link>
    </main>
  );
}
