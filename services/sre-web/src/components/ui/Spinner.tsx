/**
 * Spinner — loading indicator using brand.primary color.
 * Used inside Button (loading state) and for page-level loading.
 */
import { clsx } from 'clsx'

type SpinnerSize = 'sm' | 'md' | 'lg'

interface SpinnerProps {
  size?: SpinnerSize
  className?: string
  label?: string
}

const sizeClasses: Record<SpinnerSize, string> = {
  sm: 'w-4 h-4 border-2',
  md: 'w-6 h-6 border-2',
  lg: 'w-10 h-10 border-4',
}

export function Spinner({ size = 'md', className, label = 'Loading...' }: SpinnerProps) {
  return (
    <span
      role="status"
      aria-label={label}
      className={clsx(
        'inline-block rounded-full border-current border-t-transparent animate-spin text-brand-primary',
        sizeClasses[size],
        className,
      )}
    />
  )
}
