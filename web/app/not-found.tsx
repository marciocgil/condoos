import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6">
      <p className="text-sm font-semibold tracking-wide text-brand-600">CondoOS</p>
      <h1 className="mt-1 text-xl font-semibold">Página não encontrada</h1>
      <p className="mt-2 text-sm text-gray-600">
        O endereço não existe ou você não tem acesso a ele.
      </p>
      <Link href="/" className="mt-4 font-medium text-brand-600 underline">
        Voltar ao início
      </Link>
    </main>
  );
}
