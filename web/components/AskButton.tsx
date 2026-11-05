import { MessageSquare } from "lucide-react";

/** "Pergunte ao CondoOS" — always visible; the chat itself arrives in milestone 5. */
export function AskButton() {
  return (
    <button
      type="button"
      disabled
      title="Disponível em breve"
      className="fixed right-4 bottom-20 z-20 inline-flex h-11 items-center gap-2 rounded-full border border-info/70 bg-bg-2 px-4 text-sm font-medium text-fg disabled:cursor-not-allowed"
    >
      <MessageSquare size={16} aria-hidden className="text-info" />
      Pergunte ao CondoOS
      <span className="sr-only">(disponível em breve)</span>
    </button>
  );
}
