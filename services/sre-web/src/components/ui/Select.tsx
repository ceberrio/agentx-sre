/**
 * Select — dropdown with label, options array, and error state.
 */
import { type SelectHTMLAttributes } from 'react'
import { clsx } from 'clsx'

interface SelectOption {
  value: string
  label: string
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label: string
  options: SelectOption[]
  placeholder?: string
  error?: string
  helperText?: string
}

export function Select({
  label,
  options,
  placeholder,
  error,
  helperText,
  id,
  className,
  ...rest
}: SelectProps) {
  const selectId = id ?? label.toLowerCase().replace(/\s+/g, '-')
  const hasError = Boolean(error)

  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={selectId}
        className="text-sm font-medium text-neutral-700 font-montserrat"
      >
        {label}
      </label>

      <select
        id={selectId}
        aria-invalid={hasError}
        aria-describedby={hasError ? `${selectId}-error` : undefined}
        className={clsx(
          'w-full rounded-sm border px-3 py-2 text-sm text-neutral-900 font-montserrat bg-white',
          'focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-brand-primary',
          'transition-colors duration-150',
          hasError
            ? 'border-semantic-error focus:ring-semantic-error'
            : 'border-neutral-300 hover:border-neutral-400',
          className,
        )}
        {...rest}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {hasError && (
        <p id={`${selectId}-error`} role="alert" className="text-sm text-semantic-error">
          {error}
        </p>
      )}

      {!hasError && helperText && (
        <p className="text-sm text-neutral-500">{helperText}</p>
      )}
    </div>
  )
}
