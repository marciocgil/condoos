import { z } from "zod";

/**
 * Editable props (Remotion Studio → right panel). Headlines: " / " breaks a line and
 * *asterisks* mark the emphasised words.
 */
export const filmSchema = z.object({
  headlines: z.object({
    leak: z.string(),
    drift: z.string(),
    scan: z.string(),
    layers: z.string(),
    review: z.string(),
    impact: z.string(),
    sealed: z.string(),
  }),
  brand: z.object({
    tagline1: z.string(),
    tagline2: z.string(),
  }),
  demoLabel: z.string(),
  showHud: z.boolean(),
  /** File in public/, e.g. "assets/audio/trilha.mp3". Empty = silent film. */
  audioSrc: z.string(),
  audioVolume: z.number().min(0).max(1),
});

export type FilmProps = z.infer<typeof filmSchema>;

export const defaultFilmProps: FilmProps = {
  headlines: {
    leak: "Nem todo vazamento / faz *barulho.*",
    drift: "Alguns aparecem / no orçamento. / *Todo mês.*",
    scan: "E se fosse possível / encontrar o que / *ninguém percebeu?*",
    layers: "Uma inteligência / que analisa seus / *contratos.*",
    review: "Detecta. Prioriza. / *Recomenda.*",
    impact: "Do diagnóstico / à *decisão.*",
    sealed: "Mais controle. / Menos *desperdício.*",
  },
  brand: {
    tagline1: "Menos desperdício.",
    tagline2: "Mais inteligência para seu condomínio.",
  },
  demoLabel: "Dados de demonstração",
  showHud: true,
  audioSrc: "",
  audioVolume: 0.8,
};
