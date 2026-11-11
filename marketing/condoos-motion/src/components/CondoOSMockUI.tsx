/**
 * Visual-only reconstructions of the real CondoOS components (web/components/ui and
 * web/components/condoos): same tokens, radii, labels and icons, no data fetching and no
 * business logic. Sizes are in "app pixels"; wrap them in <AppScale> to enlarge for 1080p.
 */
import {
  Banknote,
  Calculator,
  CircleDashed,
  Eye,
  FileSignature,
  FileText,
  Hourglass,
  CheckSquare,
  FolderKanban,
  Inbox,
  LayoutGrid,
  PiggyBank,
  Receipt,
  Settings,
  ShieldCheck,
  Store,
  Sun,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { brl } from "../data/format";
import type { Opportunity } from "../data/demoFixtures";
import { alpha, C, FONT, RADIUS } from "../design/condoosTokens";

export function AppScale({
  scale,
  width,
  children,
  style,
}: {
  scale: number;
  width: number; // in app px
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div style={{ width: width * scale, ...style }}>
      <div
        style={{
          width,
          transform: `scale(${scale})`,
          transformOrigin: "top left",
          fontFamily: FONT,
          fontSize: 14,
          color: C.fg,
        }}
      >
        {children}
      </div>
    </div>
  );
}

/** layout/Logo.tsx: lime square with the "C" and the word mark. */
export function Logo({ size = 28, compact = false }: { size?: number; compact?: boolean }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: size * 0.3 }}>
      <span
        style={{
          width: size,
          height: size,
          borderRadius: size * 0.29,
          background: C.accent,
          color: C.accentFg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 700,
          fontSize: size * 0.47,
        }}
      >
        C
      </span>
      {!compact && (
        <span style={{ fontWeight: 600, letterSpacing: "-0.02em", fontSize: size * 0.57 }}>
          CondoOS
        </span>
      )}
    </span>
  );
}

export type Tone = "danger" | "warning" | "success" | "info" | "neutral" | "accent";
const TONE: Record<Tone, { border: string; color: string }> = {
  danger: { border: alpha(C.danger, 0.6), color: C.danger },
  warning: { border: alpha(C.warning, 0.6), color: C.warning },
  success: { border: alpha(C.success, 0.6), color: C.success },
  info: { border: alpha(C.info, 0.6), color: C.info },
  neutral: { border: C.control, color: C.fg2 },
  accent: { border: alpha(C.accent, 0.7), color: C.accent },
};

/** ui/Badge.tsx: always text, usually an icon, never colour alone. */
export function Badge({
  tone,
  icon,
  children,
  style,
}: {
  tone: Tone;
  icon?: ReactNode;
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        borderRadius: 999,
        border: `1px solid ${TONE[tone].border}`,
        color: TONE[tone].color,
        padding: "2px 10px",
        fontSize: 12,
        fontWeight: 500,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {icon}
      {children}
    </span>
  );
}

const STATUS: Record<string, { tone: Tone; icon: ReactNode; label: string }> = {
  identificada: { tone: "neutral", icon: <CircleDashed size={12} />, label: "Identificada" },
  em_revisao_interna: {
    tone: "warning",
    icon: <Hourglass size={12} />,
    label: "Em revisão CondoOS",
  },
  aprovada_para_cliente: {
    tone: "accent",
    icon: <Eye size={12} />,
    label: "Apresentada ao condomínio",
  },
  aprovada_pelo_condominio: {
    tone: "success",
    icon: <ShieldCheck size={12} />,
    label: "Aprovada pelo condomínio",
  },
};

/** condoos/OpportunityStatusBadge.tsx (labels from web/lib/labels.ts). */
export function OpportunityStatusBadge({
  status,
  style,
}: {
  status: keyof typeof STATUS;
  style?: CSSProperties;
}) {
  const s = STATUS[status];
  return (
    <Badge tone={s.tone} icon={s.icon} style={style}>
      {s.label}
    </Badge>
  );
}

/** condoos/OpportunityCards.tsx: one card. */
export function OpportunityCard({
  o,
  status = "identificada",
  highlight = 0,
  style,
}: {
  o: Opportunity;
  status?: keyof typeof STATUS;
  highlight?: number; // 0..1 accent border (selected)
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        borderRadius: RADIUS.card,
        border: `1px solid ${highlight > 0 ? alpha(C.accent, 0.3 + 0.5 * highlight) : C.line}`,
        background: highlight > 0 ? C.elevated : C.surface,
        padding: 16,
        boxShadow: highlight > 0 ? `0 0 ${24 * highlight}px ${alpha(C.accent, 0.18)}` : "none",
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 12, color: C.muted, fontVariantNumeric: "tabular-nums" }}>
          {o.number}
        </span>
        <OpportunityStatusBadge status={status} />
      </div>
      <div style={{ marginTop: 4, fontWeight: 500 }}>{o.title}</div>
      <div style={{ marginTop: 4, fontSize: 13, color: C.fg2 }}>
        Economia potencial identificada:{" "}
        <span style={{ color: C.fg, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>
          {brl(o.annual)} por ano
        </span>
      </div>
      <div style={{ marginTop: 2, fontSize: 12, color: C.muted }}>
        {o.type} · {o.supplier}
      </div>
    </div>
  );
}

/** ui/Card.tsx + CardTitle. */
export function Card({
  title,
  children,
  tone = "default",
  style,
}: {
  title?: string;
  children: ReactNode;
  tone?: "default" | "highlight";
  style?: CSSProperties;
}) {
  return (
    <section
      style={{
        borderRadius: RADIUS.card,
        border: `1px solid ${tone === "highlight" ? alpha(C.accent, 0.6) : C.line}`,
        background: C.surface,
        padding: 20,
        ...style,
      }}
    >
      {title && <h2 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600 }}>{title}</h2>}
      {children}
    </section>
  );
}

/** condoos/SavingsStages.tsx: one stage card, never summed with other stages. */
export function SavingsStageCard({
  o,
  value,
}: {
  o: Opportunity;
  value?: number; // animated annual value
}) {
  return (
    <div
      style={{
        borderRadius: RADIUS.card,
        border: `1px solid ${C.line}`,
        background: C.surface,
        padding: 16,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: C.fg2 }}>
          Economia potencial identificada
        </span>
        <Badge tone="success" icon={<Calculator size={12} />}>
          Confiança alta
        </Badge>
      </div>
      <div
        style={{
          marginTop: 4,
          fontSize: 24,
          fontWeight: 600,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {brl(value ?? o.annual)}{" "}
        <span style={{ fontSize: 14, fontWeight: 400, color: C.fg2 }}>por ano</span>
      </div>
      <div style={{ fontSize: 13, color: C.fg2, fontVariantNumeric: "tabular-nums" }}>
        {brl(o.monthly)} por mês · custo para implementar R$ 0,00 · líquido {brl(o.monthly)}
      </div>
      <div style={{ marginTop: 4, fontSize: 12, color: C.muted }}>
        Método reajuste_indice_v1 · base: faturas de mar. a out. de 2026
      </div>
    </div>
  );
}

/** ui/Button.tsx variants used in the film. */
export function Button({
  variant,
  children,
  pressed = 0,
  style,
}: {
  variant: "primary" | "secondary" | "danger" | "ghost";
  children: ReactNode;
  pressed?: number;
  style?: CSSProperties;
}) {
  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    height: 40,
    padding: "0 16px",
    borderRadius: RADIUS.button,
    fontSize: 14,
    fontWeight: 500,
    transform: `scale(${1 - pressed * 0.05})`,
  };
  const v: Record<string, CSSProperties> = {
    primary: { background: pressed ? "#C8EB00" : C.accent, color: C.accentFg },
    secondary: { border: `1px solid ${C.control}`, color: C.fg },
    danger: { border: `1px solid ${alpha(C.danger, 0.6)}`, color: C.danger },
    ghost: { color: C.fg2 },
  };
  return <span style={{ ...base, ...v[variant], ...style }}>{children}</span>;
}

const EVIDENCE_ICON: Record<string, ReactNode> = {
  contract: <FileSignature size={16} />,
  document: <Receipt size={16} />,
  bank: <Banknote size={16} />,
  file: <FileText size={16} />,
};

/** condoos/EvidenceList.tsx: one item. */
export function EvidenceItem({
  icon,
  label,
  excerpt,
  style,
}: {
  icon: string;
  label: string;
  excerpt?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        borderRadius: RADIUS.card,
        border: `1px solid ${C.line}`,
        background: C.bg2,
        padding: "12px 16px",
        ...style,
      }}
    >
      <span style={{ color: C.fg2, marginTop: 2, display: "inline-flex" }}>
        {EVIDENCE_ICON[icon]}
      </span>
      <span style={{ flex: 1 }}>
        <span style={{ display: "block", fontSize: 14, fontVariantNumeric: "tabular-nums" }}>
          {label}
        </span>
        {excerpt && (
          <span style={{ display: "block", marginTop: 2, fontSize: 13, color: C.fg2 }}>
            {excerpt}
          </span>
        )}
      </span>
      <span style={{ fontSize: 12, color: C.accent }}>Abrir documento</span>
    </div>
  );
}

/** ui/KpiCard.tsx */
export function KpiCard({
  label,
  value,
  context,
  icon,
  tone = "normal",
  style,
}: {
  label: string;
  value: ReactNode;
  context?: ReactNode;
  icon?: ReactNode;
  tone?: "normal" | "positive";
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        borderRadius: RADIUS.card,
        border: `1px solid ${tone === "positive" ? alpha(C.success, 0.5) : C.line}`,
        background: C.surface,
        padding: 20,
        ...style,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 13,
          fontWeight: 500,
          color: C.fg2,
        }}
      >
        <span>{label}</span>
        {icon && <span style={{ color: C.muted, display: "inline-flex" }}>{icon}</span>}
      </div>
      <div
        style={{
          marginTop: 8,
          fontSize: 28,
          lineHeight: 1.15,
          fontWeight: 600,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
      {context && <div style={{ marginTop: 4, fontSize: 13, color: C.fg2 }}>{context}</div>}
    </div>
  );
}

// Same items, order and icons as web/components/AdminNav.tsx (subset that fits the frame).
const NAV = [
  { label: "Hoje", icon: <Sun size={18} /> },
  { label: "Carteira", icon: <LayoutGrid size={18} /> },
  { label: "Fila de exceções", icon: <Inbox size={18} /> },
  { label: "Assuntos", icon: <FolderKanban size={18} /> },
  { label: "Oportunidades", icon: <PiggyBank size={18} /> },
  { label: "Aprovações", icon: <CheckSquare size={18} /> },
  { label: "Fornecedores", icon: <Store size={18} /> },
  { label: "Contratos", icon: <FileSignature size={18} /> },
  { label: "Configurações", icon: <Settings size={18} /> },
];

/** Admin app shell (AdminNav sidebar + header), as in docs/screens/admin-*.png. */
export function AdminShell({
  active,
  title,
  children,
  width,
  height,
}: {
  active: string;
  title: string;
  children: ReactNode;
  width: number;
  height: number;
}) {
  return (
    <div
      style={{
        width,
        height,
        display: "flex",
        background: C.bg,
        borderRadius: RADIUS.panel,
        overflow: "hidden",
        border: `1px solid ${C.line}`,
      }}
    >
      <aside
        style={{
          width: 200,
          borderRight: `1px solid ${C.line}`,
          padding: "16px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <div style={{ padding: "0 6px 14px" }}>
          <Logo size={24} />
        </div>
        {NAV.map((n) => {
          const on = n.label === active;
          return (
            <div
              key={n.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 10px",
                borderRadius: RADIUS.control,
                background: on ? alpha(C.accent, 0.1) : "transparent",
                color: on ? C.accent : C.fg2,
                fontSize: 13,
                fontWeight: on ? 600 : 400,
              }}
            >
              {n.icon}
              {n.label}
            </div>
          );
        })}
      </aside>
      <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <header
          style={{
            height: 48,
            borderBottom: `1px solid ${C.line}`,
            display: "flex",
            alignItems: "center",
            padding: "0 20px",
            fontSize: 13,
            color: C.fg2,
            gap: 8,
          }}
        >
          Atlântida Gestão (fictícia) <span style={{ color: C.muted }}>›</span>
          <span style={{ color: C.fg }}>{title}</span>
        </header>
        <div style={{ flex: 1, padding: 20 }}>{children}</div>
      </main>
    </div>
  );
}

/** Small "Dados de demonstração" tag used inside the UI scenes. */
export function DemoNote({ children }: { children: ReactNode }) {
  return <p style={{ margin: 0, fontSize: 12, color: C.muted }}>{children}</p>;
}
