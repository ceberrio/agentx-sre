/**
 * Toggle — boolean switch. ON = brand.primary background.
 * BR-05: transition-colors only (150ms).
 */
import { clsx } from 'clsx'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: string
  disabled?: boolean
  id?: string
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  id,
}: ToggleProps) {
  const toggleId = id ?? label.toLowerCase().replace(/\s+/g, '-')

  return (
    <div className="flex items-start gap-3">
      <button
        role="switch"
        id={toggleId}
        type="button"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={clsx(
          'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent',
          'focus:outline-none focus:ring-2 focus:ring-brand-primary focus:ring-offset-2',
          'transition-colors duration-150',
          checked ? 'bg-brand-primary' : 'bg-neutral-300',
          disabled && 'opacity-50 cursor-not-allowed',
        )}
      >
        <span
          aria-hidden="true"
          className={clsx(
            'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow',
            'transition-transform duration-150',
            checked ? 'translate-x-5' : 'translate-x-0',
          )}
        />
      </button>

      <div className="flex flex-col">
        <label
          htmlFor={toggleId}
          className={clsx(
            'text-sm font-medium font-montserrat',
            disabled ? 'text-neutral-400' : 'text-neutral-800',
            'cursor-pointer',
          )}
        >
          {label}
        </label>
        {description && (
          <p className="text-sm text-neutral-500 mt-0.5">{description}</p>
        )}
      </div>
    </div>
  )
}
