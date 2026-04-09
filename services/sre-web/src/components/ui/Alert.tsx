/**
 * Alert — inline notification for success/warning/error/info.
 * AC-10: applies semantic color tokens with corresponding lucide icons.
 * Dismissible variant via onDismiss prop.
 */
import { type ReactNode } from 'react'
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Info,
  X,
} from 'lucide-react'
import { clsx } from 'clsx'

type AlertType = 'success' | 'warning' | 'error' | 'info'

interface AlertProps {
  type: AlertType
  title?: string
  message: string
  onDismiss?: () => void
  className?: string
  children?: ReactNode
}

const alertConfig: Record<
  AlertType,
  { bg: string; border: string; text: string; icon: ReactNode }
> = {
  success: {
    bg: 'bg-semantic-success-light',
    border: 'border-semantic-success',
    text: 'text-green-800',
    icon: <CheckCircle size={18} className="text-semantic-success flex-shrink-0" />,
  },
  warning: {
    bg: 'bg-semantic-warning-light',
    border: 'border-semantic-warning',
    text: 'text-amber-800',
    icon: <AlertTriangle size={18} className="text-semantic-warning flex-shrink-0" />,
  },
  error: {
    bg: 'bg-semantic-error-light',
    border: 'border-semantic-error',
    text: 'text-red-800',
    icon: <XCircle size={18} className="text-semantic-error flex-shrink-0" />,
  },
  info: {
    bg: 'bg-semantic-info-light',
    border: 'border-semantic-info',
    text: 'text-blue-800',
    icon: <Info size={18} className="text-semantic-info flex-shrink-0" />,
  },
}

export function Alert({
  type,
  title,
  message,
  onDismiss,
  className,
  children,
}: AlertProps) {
  const config = alertConfig[type]

  return (
    <div
      role="alert"
      className={clsx(
        'flex gap-3 rounded-md border p-4',
        config.bg,
        config.border,
        className,
      )}
    >
      {config.icon}

      <div className="flex-1 min-w-0">
        {title && (
          <p className={clsx('text-sm font-semibold font-montserrat mb-1', config.text)}>
            {title}
          </p>
        )}
        <p className={clsx('text-sm font-montserrat', config.text)}>{message}</p>
        {children}
      </div>

      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss alert"
          className={clsx(
            'flex-shrink-0 rounded p-0.5 hover:bg-black/10 transition-colors duration-150',
            config.text,
          )}
        >
          <X size={16} />
        </button>
      )}
    </div>
  )
}
