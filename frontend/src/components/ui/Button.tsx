import type { ButtonHTMLAttributes, ComponentType, SVGProps } from "react";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: IconComponent;
  variant?: "primary" | "secondary" | "ghost";
};

export default function Button({
  children,
  className = "",
  icon: Icon,
  variant = "primary",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`button button--${variant} ${className}`.trim()}
      type={type}
      {...props}
    >
      {Icon ? <Icon aria-hidden="true" /> : null}
      {children}
    </button>
  );
}
