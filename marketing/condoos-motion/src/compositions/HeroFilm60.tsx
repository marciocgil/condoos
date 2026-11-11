import { BrandOutro } from "../scenes/BrandOutro";
import { ContractAnalysis } from "../scenes/ContractAnalysis";
import { CostDrift } from "../scenes/CostDrift";
import { ImpactDashboard } from "../scenes/ImpactDashboard";
import { LayeredProduct } from "../scenes/LayeredProduct";
import { LeakMetaphor } from "../scenes/LeakMetaphor";
import { OpportunityReview } from "../scenes/OpportunityReview";
import { SealedBuilding } from "../scenes/SealedBuilding";
import type { FilmProps } from "../schema";
import { Film, type Segment } from "./Film";

export const HERO60_FRAMES = 1800; // 60 s at 30 fps

/** Master: 60 s, 1080 × 1920. Scenes overlap by 8–10 frames for the cross-fades. */
export function HeroFilm60(props: FilmProps) {
  const h = props.headlines;
  const segments: Segment[] = [
    {
      name: "01 Vazamento",
      chapter: "01 · O PROBLEMA",
      from: 0,
      dur: 180,
      fadeIn: 0,
      fadeOut: 8,
      render: () => <LeakMetaphor headline={h.leak} />,
    },
    {
      name: "02 Custo que cresce",
      chapter: "01 · O PROBLEMA",
      from: 172,
      dur: 200,
      render: () => <CostDrift headline={h.drift} />,
    },
    {
      name: "03 Análise do contrato",
      chapter: "02 · ANÁLISE DE CONTRATOS",
      from: 362,
      dur: 250,
      render: () => <ContractAnalysis headline={h.scan} />,
    },
    {
      name: "04 Produto em camadas",
      chapter: "03 · CONDOOS OPTIMIZE",
      from: 602,
      dur: 270,
      render: () => <LayeredProduct headline={h.layers} />,
    },
    {
      name: "05 Oportunidades e revisão",
      chapter: "04 · REVISÃO INTERNA",
      from: 862,
      dur: 300,
      render: () => <OpportunityReview headline={h.review} />,
    },
    {
      name: "06 Impacto e decisão",
      chapter: "05 · DECISÃO DO CONDOMÍNIO",
      from: 1152,
      dur: 300,
      render: () => <ImpactDashboard headline={h.impact} />,
    },
    {
      name: "07 Prédio selado",
      chapter: "06 · CONTROLE",
      from: 1442,
      dur: 180,
      fadeOut: 0,
      render: () => <SealedBuilding headline={h.sealed} />,
    },
    {
      name: "08 Assinatura",
      chapter: "",
      from: 1612,
      dur: 188,
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
