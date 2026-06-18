import type { ButtonHTMLAttributes, ComponentType, SVGProps } from "react";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-busy"> & {
  icon?: IconComponent;
  loading?: boolean;
  variant?: "primary" | "secondary" | "ghost";
};

export default function Button({
  "aria-busy": _ariaBusy,
  children,
  className = "",
  disabled,
  icon: Icon,
  loading = false,
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps & { "aria-busy"?: never }) {
  return (
    <button
      aria-busy={loading ? true : undefined}
      className={`button button--${variant} ${className}`.trim()}
      disabled={disabled || loading}
      type={type}
      {...props}
    >
      {loading
        ? <span aria-hidden="true" className="button__spinner" />
        : Icon
          ? <Icon aria-hidden="true" />
          : null}
      {children}
    </button>
  );
}
