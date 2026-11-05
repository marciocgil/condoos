import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type Size = "md" | "sm";

const VARIANT: Record<ButtonVariant, string> = {
  // Lime accent is reserved for the primary action (DS §2.1).
  primary: "bg-accent text-accent-fg hover:bg-accent-hover",
  secondary: "border border-control bg-surface text-fg hover:bg-elevated",
  ghost: "text-fg-2 hover:bg-surface hover:text-fg",
  danger: "border border-danger/60 bg-transparent text-danger hover:bg-danger/10",
};
const SIZE: Record<Size, string> = {
  md: "h-10 px-4 text-sm",
  sm: "h-8 px-3 text-[13px]",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: Size = "md"): string {
  return cx(
    "transition-ui inline-flex items-center justify-center gap-2 rounded-[var(--radius-button)] font-medium whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-50",
    VARIANT[variant],
    SIZE[size],
  );
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: Size;
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  className,
  children,
  ...rest
}: Props) {
  return (
    <button type="button" {...rest} className={cx(buttonClass(variant, size), className)}>
      {icon}
      {children}
    </button>
  );
}

export function ButtonLink({
  href,
  variant = "secondary",
  size = "md",
  icon,
  className,
  children,
}: {
  href: string;
  variant?: ButtonVariant;
  size?: Size;
  icon?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={cx(buttonClass(variant, size), className)}>
      {icon}
      {children}
    </Link>
  );
}
