import { AlertOctagon, AlertTriangle, Info } from "lucide-react";

import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { SEVERITY_LABEL } from "@/lib/labels";
import type { Severity } from "@/lib/types";

const TONE: Record<Severity, BadgeTone> = { alta: "danger", media: "warning", baixa: "info" };
const ICON = {
  alta: <AlertOctagon size={12} />,
  media: <AlertTriangle size={12} />,
  baixa: <Info size={12} />,
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge tone={TONE[severity]} icon={ICON[severity]}>
      {SEVERITY_LABEL[severity]}
    </Badge>
  );
}

export const SEVERITY_DOT: Record<Severity, string> = {
  alta: "bg-danger",
  media: "bg-warning",
  baixa: "bg-info",
};
