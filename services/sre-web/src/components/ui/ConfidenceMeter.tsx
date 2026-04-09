/**
 * ConfidenceMeter — visual progress bar for confidence scores (0.0–1.0).
 * Color thresholds: green > 0.7, yellow 0.5–0.7, red < 0.5.
 */
import { clsx } from 'clsx'

interface ConfidenceMeterProps {
  value: number
  showLabel?: boolean
  className?: string
}

function getColorClass(value: number): string {
  if (value >= 0.7) return 'bg-semantic-success'
  if (value >= 0.5) return 'bg-semantic-warning'
  return 'bg-semantic-error'
}

function getLabelColorClass(value: number): string {
  if (value >= 0.7) return 'text-green-700'
  if (value >= 0.5) return 'text-amber-700'
  return 'text-red-700'
}

export function ConfidenceMeter({
  value,
  showLabel = true,
  className,
}: ConfidenceMeterProps) {
  const clamped = Math.min(1, Math.max(0, value))
  const pct = Math.round(clamped * 100)

  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Confidence: ${pct}%`}
        className="flex-1 h-2 bg-neutral-200 rounded-full overflow-hidden"
      >
        <div
          className={clsx('h-full rounded-full transition-all duration-150', getColorClass(clamped))}
          style={{ width: `${pct}%` }}
        />
      </div>

      {showLabel && (
        <span
          className={clsx(
            'text-xs font-semibold font-montserrat w-10 text-right',
            getLabelColorClass(clamped),
          )}
        >
          {pct}%
        </span>
      )}
    </div>
  )
}
