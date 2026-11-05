/** "Pergunte ao CondoOS" — always visible. The chat itself arrives in milestone 5. */
export function AskButton() {
  return (
    <button
      type="button"
      disabled
      title="Disponível em breve"
      className="fixed right-4 bottom-20 z-10 rounded-full bg-brand-600 px-4 py-3 text-sm font-medium text-white shadow-lg disabled:opacity-80"
    >
      Pergunte ao CondoOS
    </button>
  );
}
