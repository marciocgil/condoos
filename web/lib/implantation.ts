/** Implantation of a condominium (D128): the eight items and their state. */
export type ImplantationItem = {
  key: string;
  title: string;
  why: string;
  done: boolean;
  detail: string;
  action: "mandato" | "termo" | "alcada" | "enviar";
};

export type Implantation = {
  condominium: { id: string; name: string };
  items: ImplantationItem[];
  done: number;
  total: number;
  percent: number;
  complete: boolean;
  next: ImplantationItem | null;
  recommended: { key: string; title: string; done: boolean }[];
  can_manage: boolean;
};
