/**
 * Card — container section with SoftServe tokens.
 * AC-08: white bg, border-radius 8px, shadow-sm, padding 16px.
 * Hover: shadow scales to shadow-md. BR-05: transition-shadow only.
 */
import { type ReactNode } from 'react'
import { clsx } from 'clsx'

type CardPadding = 'none' | 'sm' | 'md' | 'lg'

interface CardProps {
  children: ReactNode
  padding?: CardPadding
  hoverable?: boolean
  className?: string
  /** Optional header: title + action slot */
  title?: string
  action?: ReactNode
}

const paddingClasses: Record<CardPadding, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}

export function Card({
  children,
  padding = 'md',
  hoverable = false,
  className,
  title,
  action,
}: CardProps) {
  return (
    <div
      className={clsx(
        'bg-white rounded-md shadow-sm',
        'transition-shadow duration-150',
        hoverable && 'hover:shadow-md cursor-pointer',
        className,
      )}
    >
      {(title ?? action) && (
        <div
          className={clsx(
            'flex items-center justify-between border-b border-neutral-100 px-4 py-3',
          )}
        >
          {title && (
            <h3 className="text-base font-semibold text-neutral-900 font-montserrat">
              {title}
            </h3>
          )}
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      <div className={paddingClasses[padding]}>{children}</div>
    </div>
  )
}
