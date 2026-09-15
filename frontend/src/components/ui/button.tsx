import clsx from "clsx";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const variants: Record<Variant, string> = {
  primary:
    "bg-amber-500 text-stone-950 hover:bg-amber-400 disabled:bg-stone-600 disabled:text-stone-400",
  secondary:
    "bg-stone-800 text-stone-100 border border-stone-600 hover:bg-stone-700",
  ghost: "bg-transparent text-stone-300 hover:bg-stone-800/80",
  danger: "bg-red-900/80 text-red-100 hover:bg-red-800",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
