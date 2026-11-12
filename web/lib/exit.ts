/** The síndico's exit (D129): GET /condominiums/{id}/exit. */
export type ExitInfo = {
  condominium: { id: string; name: string };
  can_exit: boolean;
  pending: { on: string; reason: string } | null;
  today: string;
  max_date: string;
  mandate_end: string | null;
  retention_years: number;
  reasons: { key: string; label: string }[];
};
