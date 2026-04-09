/**
 * Input — text field with label, helper text, error state, and password toggle.
 * Uses neutral palette for borders; semantic.error for validation state.
 */
import { type InputHTMLAttributes, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { clsx } from 'clsx'

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
  helperText?: string
  error?: string | undefined
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url' | 'search'
}

export function Input({
  label,
  helperText,
  error,
  type = 'text',
  id,
  className,
  ...rest
}: InputProps) {
  const [showPassword, setShowPassword] = useState(false)
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, '-')
  const isPassword = type === 'password'
  const resolvedType = isPassword && showPassword ? 'text' : type
  const hasError = Boolean(error)

  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={inputId}
        className="text-sm font-medium text-neutral-700 font-montserrat"
      >
        {label}
      </label>

      <div className="relative">
        <input
          id={inputId}
          type={resolvedType}
          aria-invalid={hasError}
          aria-describedby={
            hasError ? `${inputId}-error` : helperText ? `${inputId}-helper` : undefined
          }
          className={clsx(
            'w-full rounded-sm border px-3 py-2 text-sm text-neutral-900 font-montserrat',
            'placeholder:text-neutral-400',
            'focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-brand-primary',
            'transition-colors duration-150',
            hasError
              ? 'border-semantic-error focus:ring-semantic-error'
              : 'border-neutral-300 hover:border-neutral-400',
            isPassword ? 'pr-10' : '',
            className,
          )}
          {...rest}
        />

        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-neutral-700"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        )}
      </div>

      {hasError && (
        <p id={`${inputId}-error`} role="alert" className="text-sm text-semantic-error">
          {error}
        </p>
      )}

      {!hasError && helperText && (
        <p id={`${inputId}-helper`} className="text-sm text-neutral-500">
          {helperText}
        </p>
      )}
    </div>
  )
}
