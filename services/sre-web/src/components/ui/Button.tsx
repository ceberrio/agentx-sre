/**
 * Button — base interactive element using SoftServe design tokens.
 * AC-06: variants primary, secondary, danger. Ghost added for utility.
 * BR-05: only transition-colors (150ms), no complex animations.
 */
import { type ButtonHTMLAttributes, type ReactNode } from 'react'
import { clsx } from 'clsx'
import { Spinner } from './Spinner'

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: ReactNode
  children: ReactNode
}

const variantClasses: Record<ButtonVariant, string> = {
  // AC-06: primary = #454494 bg, white text
  primary:
    'bg-brand-primary text-white hover:bg-brand-dark focus:ring-2 focus:ring-brand-primary focus:ring-offset-2 disabled:bg-neutral-300 disabled:cursor-not-allowed',
  // AC-06: secondary = border #454494, transparent bg, #454494 text
  secondary:
    'border-2 border-brand-primary text-brand-primary bg-transparent hover:bg-brand-lighter focus:ring-2 focus:ring-brand-primary focus:ring-offset-2 disabled:border-neutral-300 disabled:text-neutral-400 disabled:cursor-not-allowed',
  // AC-06: danger = #EF4444 bg (semantic.error), white text
  danger:
    'bg-semantic-error text-white hover:bg-red-600 focus:ring-2 focus:ring-semantic-error focus:ring-offset-2 disabled:bg-neutral-300 disabled:cursor-not-allowed',
  ghost:
    'text-brand-primary bg-transparent hover:bg-brand-lighter focus:ring-2 focus:ring-brand-primary focus:ring-offset-2 disabled:text-neutral-400 disabled:cursor-not-allowed',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm rounded-sm font-medium',
  md: 'px-4 py-2 text-base rounded-sm font-medium',
  lg: 'px-6 py-3 text-lg rounded-md font-semibold',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  disabled,
  className,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled ?? loading

  return (
    <button
      disabled={isDisabled}
      className={clsx(
        'inline-flex items-center justify-center gap-2 font-montserrat transition-colors duration-150',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      aria-busy={loading}
      {...rest}
    >
      {loading ? (
        <Spinner
          size="sm"
          className={variant === 'primary' || variant === 'danger' ? 'text-white' : 'text-brand-primary'}
        />
      ) : (
        icon && <span className="flex-shrink-0">{icon}</span>
      )}
      {children}
    </button>
  )
}
