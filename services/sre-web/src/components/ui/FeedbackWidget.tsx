/**
 * FeedbackWidget — thumbs up/down + neutral with optional comment textarea.
 * Shows "Feedback submitted" confirmation state after submission.
 */
import { useState } from 'react'
import { ThumbsUp, ThumbsDown, Send } from 'lucide-react'
import { clsx } from 'clsx'
import type { FeedbackRating } from '../../api/types'
import { Button } from './Button'

interface FeedbackWidgetProps {
  incidentId: string
  onSubmit: (rating: FeedbackRating, comment?: string) => Promise<void>
  className?: string
}

interface RatingButtonProps {
  rating: FeedbackRating
  selected: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}

function RatingButton({ rating: _rating, selected, onClick, icon, label }: RatingButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={selected}
      className={clsx(
        'flex items-center justify-center w-10 h-10 rounded-md border-2 transition-colors duration-150',
        selected
          ? 'border-brand-primary bg-brand-lighter text-brand-primary'
          : 'border-neutral-200 bg-white text-neutral-500 hover:border-brand-primary hover:text-brand-primary',
      )}
    >
      {icon}
    </button>
  )
}

export function FeedbackWidget({
  incidentId: _incidentId,
  onSubmit,
  className,
}: FeedbackWidgetProps) {
  const [selectedRating, setSelectedRating] = useState<FeedbackRating | null>(null)
  const [comment, setComment] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    if (!selectedRating) return
    setIsSubmitting(true)
    setError(null)
    try {
      await onSubmit(selectedRating, comment.trim() || undefined)
      setSubmitted(true)
    } catch {
      setError('Failed to submit feedback. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 text-semantic-success text-sm font-medium font-montserrat',
          className,
        )}
        role="status"
      >
        <ThumbsUp size={16} />
        <span>Feedback submitted. Thank you!</span>
      </div>
    )
  }

  return (
    <div className={clsx('space-y-3', className)}>
      <p className="text-sm font-medium text-neutral-700 font-montserrat">
        Was this triage helpful?
      </p>

      {/* Rating buttons */}
      <div className="flex gap-2">
        <RatingButton
          rating="positive"
          selected={selectedRating === 'positive'}
          onClick={() => setSelectedRating('positive')}
          icon={<ThumbsUp size={18} />}
          label="Positive feedback"
        />
        <RatingButton
          rating="negative"
          selected={selectedRating === 'negative'}
          onClick={() => setSelectedRating('negative')}
          icon={<ThumbsDown size={18} />}
          label="Negative feedback"
        />
      </div>

      {/* Optional comment */}
      {selectedRating && (
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Optional: add a comment..."
          rows={3}
          className={clsx(
            'w-full rounded-sm border border-neutral-300 px-3 py-2 text-sm font-montserrat',
            'text-neutral-900 placeholder:text-neutral-400',
            'focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-brand-primary',
            'transition-colors duration-150 resize-none',
          )}
          aria-label="Feedback comment"
        />
      )}

      {error && (
        <p role="alert" className="text-sm text-semantic-error font-montserrat">
          {error}
        </p>
      )}

      <Button
        variant="primary"
        size="sm"
        disabled={!selectedRating}
        loading={isSubmitting}
        onClick={handleSubmit}
        icon={<Send size={14} />}
      >
        Submit Feedback
      </Button>
    </div>
  )
}
