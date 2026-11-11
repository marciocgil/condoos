import { BrandOutro } from "../scenes/BrandOutro";
import { ContractAnalysis } from "../scenes/ContractAnalysis";
import { LeakMetaphor } from "../scenes/LeakMetaphor";
import { OpportunityReview } from "../scenes/OpportunityReview";
import { SealedBuilding } from "../scenes/SealedBuilding";
import type { FilmProps } from "../schema";
import { Film, type Segment } from "./Film";

export const HERO15_FRAMES = 450; // 15 s at 30 fps

/**
 * Cut-down: the same scenes, faster (`speed`) or trimmed (`startAt`, in base frames).
 * Hook → scan → review approval → sealed building → signature.
 */
export function HeroFilm15(props: FilmProps) {
  const h = props.headlines;
  const segments: Segment[] = [
    {
      name: "01 Vazamento",
      chapter: "01 · O PROBLEMA",
      from: 0,
      dur: 100,
      speed: 1.8,
      fadeIn: 0,
      fadeOut: 8,
      render: () => <LeakMetaphor headline={h.leak} />,
    },
    {
      name: "03 Análise do contrato",
      chapter: "02 · ANÁLISE DE CONTRATOS",
      from: 92,
      dur: 120,
      speed: 2.08,
      render: () => <ContractAnalysis headline={h.scan} />,
    },
    {
      name: "05 Revisão",
      chapter: "04 · REVISÃO INTERNA",
      from: 204,
      dur: 110,
      startAt: 140,
      speed: 1.3,
      render: () => <OpportunityReview headline={h.review} />,
    },
    {
      name: "07 Prédio selado",
      chapter: "06 · CONTROLE",
      from: 306,
      dur: 60,
      startAt: 40,
      speed: 2,
      fadeOut: 0,
      render: () => <SealedBuilding headline={h.sealed} />,
    },
    {
      name: "08 Assinatura",
      chapter: "",
      from: 358,
      dur: 92,
      speed: 1.45,
      fadeIn: 0,
      fadeOut: 0,
      render: () => (
        <BrandOutro
          tagline1={props.brand.tagline1}
          tagline2={props.brand.tagline2}
          demoLabel={props.demoLabel}
        />
      ),
    },
  ];
  return <Film segments={segments} props={props} />;
}
