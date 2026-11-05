export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold tracking-tight">
      <span
        aria-hidden
        className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-[13px] font-bold text-accent-fg"
      >
        C
      </span>
      {!compact && <span>CondoOS</span>}
    </span>
  );
}
