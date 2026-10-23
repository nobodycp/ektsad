import type { ButtonHTMLAttributes } from "react"

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger"

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: "md" | "sm"
  loading?: boolean
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  type = "button",
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      className={className ? `ds-btn ${className}` : "ds-btn"}
      data-variant={variant}
      data-size={size}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading && <span className="ds-btn__spinner" aria-hidden="true" />}
      {children}
    </button>
  )
}
