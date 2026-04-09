/**
 * RagSourceCard — displays a RAG attribution source with relevance score bar.
 * Used in incident detail view for explainability.
 */
import { FileText } from 'lucide-react'
import { clsx } from 'clsx'
import type { RagAttribution } from '../../api/types'

interface RagSourceCardProps {
  attribution: RagAttribution
  className?: string
}

export function RagSourceCard({ attribution, className }: RagSourceCardProps) {
  const relevancePct = Math.round(attribution.relevance_score * 100)

  return (
    <div
      className={clsx(
        'bg-white border border-neutral-200 rounded-md p-4 shadow-sm',
        className,
      )}
    >
      {/* Doc name */}
      <div className="flex items-center gap-2 mb-2">
        <FileText size={16} className="text-brand-primary flex-shrink-0" />
        <span className="text-sm font-semibold text-neutral-800 font-montserrat truncate">
          {attribution.doc_id}
        </span>
      </div>

      {/* Relevance score bar — brand.primary fill */}
      <div className="mb-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-neutral-500 font-montserrat">Relevance</span>
          <span className="text-xs font-semibold text-brand-primary font-montserrat">
            {relevancePct}%
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={relevancePct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Relevance: ${relevancePct}%`}
          className="h-1.5 bg-neutral-100 rounded-full overflow-hidden"
        >
          <div
            className="h-full bg-brand-primary rounded-full"
            style={{ width: `${relevancePct}%` }}
          />
        </div>
      </div>

      {/* Chunk preview — truncated */}
      <p className="text-xs text-neutral-600 font-mono line-clamp-3 bg-neutral-50 rounded p-2">
        {attribution.chunk_preview}
      </p>

      {/* Contributed to */}
      {attribution.contributed_to.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {attribution.contributed_to.map((field) => (
            <span
              key={field}
              className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-brand-lighter text-brand-primary font-montserrat"
            >
              {field}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
