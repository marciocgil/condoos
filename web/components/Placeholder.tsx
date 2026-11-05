export function Placeholder({ title, milestone }: { title: string; milestone: number }) {
  return (
    <section className="rounded-xl border border-dashed border-gray-300 bg-white p-6 text-center">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-gray-500">Esta tela chega no Marco {milestone}.</p>
    </section>
  );
}
