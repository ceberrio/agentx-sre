/**
 * NewIncidentPage — create a new SRE incident report.
 * HU-P025: Full form with real-time validation, multipart/form-data submission,
 * pipeline stage progress indicator, and redirect on success.
 */
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { FileText } from 'lucide-react'
import axios from 'axios'
import { apiClient } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PIPELINE_STAGES = [
  'Receiving incident…',
  'Analyzing with AI…',
  'Creating ticket…',
  'Sending notifications…',
]

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const ACCEPTED_FILE_TYPES = ['.txt', '.log', '.json', '.csv']
const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 // 5 MB

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Response shape from POST /incidents (pipeline result, not the Incident entity). */
interface CreateIncidentResponse {
  incident_id: string
  case_status: string
  blocked: boolean
  ticket_id: string | null
  severity: string | null
}

interface FormState {
  title: string
  reporter_email: string
  description: string
}

type FormErrors = Partial<Record<keyof FormState | 'logFile', string>>

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function validateField(
  name: keyof FormState | 'logFile',
  value: string | File | null,
): string {
  switch (name) {
    case 'title': {
      const v = (value as string).trim()
      if (!v) return 'Title is required.'
      if (v.length < 3) return 'Title must be at least 3 characters.'
      return ''
    }
    case 'reporter_email': {
      const v = (value as string).trim()
      if (!v) return 'Reporter email is required.'
      if (!EMAIL_REGEX.test(v)) return 'Enter a valid email address.'
      return ''
    }
    case 'description': {
      const v = (value as string).trim()
      if (!v) return 'Description is required.'
      if (v.length < 10) return 'Description must be at least 10 characters.'
      return ''
    }
    case 'logFile': {
      if (!value) return ''
      const file = value as File
      if (file.size > MAX_FILE_SIZE_BYTES) return 'File exceeds the 5 MB size limit.'
      const ext = '.' + file.name.split('.').pop()?.toLowerCase()
      if (!ACCEPTED_FILE_TYPES.includes(ext)) {
        return `Accepted formats: ${ACCEPTED_FILE_TYPES.join(', ')}.`
      }
      return ''
    }
    default:
      return ''
  }
}

function validateAll(form: FormState, logFile: File | null): FormErrors {
  const errors: FormErrors = {}
  const fields: Array<keyof FormState> = ['title', 'reporter_email', 'description']
  for (const field of fields) {
    const msg = validateField(field, form[field])
    if (msg) errors[field] = msg
  }
  const fileMsg = validateField('logFile', logFile)
  if (fileMsg) errors.logFile = fileMsg
  return errors
}

function hasErrors(errors: FormErrors): boolean {
  return Object.values(errors).some((v) => Boolean(v))
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NewIncidentPage() {
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)

  const [form, setForm] = useState<FormState>({
    title: '',
    reporter_email: user?.email ?? '',
    description: '',
  })
  const [logFile, setLogFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [stageIndex, setStageIndex] = useState(0)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Interval ref to clear on unmount or response arrival
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Sync reporter_email if user loads after initial render
  useEffect(() => {
    if (user?.email && !form.reporter_email) {
      setForm((prev) => ({ ...prev, reporter_email: user.email }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.email])

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  function handleFieldChange(name: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [name]: value }))
    // Clear error as user types
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }))
    }
  }

  function handleFieldBlur(name: keyof FormState) {
    const msg = validateField(name, form[name])
    setErrors((prev) => ({ ...prev, [name]: msg }))
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    setLogFile(file)
    const msg = validateField('logFile', file)
    setErrors((prev) => ({ ...prev, logFile: msg }))
  }

  function startStageTimer() {
    setStageIndex(0)
    intervalRef.current = setInterval(() => {
      setStageIndex((prev) => (prev + 1) % PIPELINE_STAGES.length)
    }, 1500)
  }

  function stopStageTimer() {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSubmitError(null)

    const validationErrors = validateAll(form, logFile)
    if (hasErrors(validationErrors)) {
      setErrors(validationErrors)
      return
    }

    setSubmitting(true)
    startStageTimer()

    try {
      const fd = new FormData()
      fd.append('reporter_email', form.reporter_email.trim())
      fd.append('title', form.title.trim())
      fd.append('description', form.description.trim())
      if (logFile) {
        fd.append('log_file', logFile)
      }

      const response = await apiClient.post<CreateIncidentResponse>('/incidents', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      navigate('/incidents/' + response.data.incident_id)
    } catch (err: unknown) {
      let message = 'Submission failed. Please try again.'
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail
        if (typeof detail === 'string' && detail.length > 0) {
          message = detail
        } else if (err.response?.status === 413) {
          message = 'The uploaded file is too large. Maximum allowed size is 5 MB.'
        } else if (err.response?.status === 422) {
          message = 'Invalid form data. Please check all fields and try again.'
        }
      }
      setSubmitError(message)
    } finally {
      stopStageTimer()
      setSubmitting(false)
    }
  }

  // -------------------------------------------------------------------------
  // Derived state
  // -------------------------------------------------------------------------

  const submitDisabled = submitting || hasErrors(errors)

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <Layout pageTitle="New Incident">
      {/* Page header */}
      <div className="flex items-center gap-3 mb-6">
        <FileText size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            Create Incident Report
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            Submit a new SRE incident for AI-assisted triage.
          </p>
        </div>
      </div>

      {/* Submission error */}
      {submitError && (
        <div className="mb-4">
          <Alert
            type="error"
            title="Submission Failed"
            message={submitError}
            onDismiss={() => setSubmitError(null)}
          />
        </div>
      )}

      {/* Processing state — replaces form while request is in-flight */}
      {submitting ? (
        <Card title="Processing Incident">
          <div className="flex flex-col items-center justify-center py-16 gap-4">
            <Spinner size="lg" label="Processing incident…" />
            <p className="text-sm font-medium text-neutral-700 font-montserrat">
              {PIPELINE_STAGES[stageIndex]}
            </p>
            <p className="text-xs text-neutral-400 font-montserrat">
              This may take up to 30 seconds.
            </p>
          </div>
        </Card>
      ) : (
        <Card title="Incident Details">
          <form
            onSubmit={(e) => void handleSubmit(e)}
            className="space-y-5 max-w-2xl"
            noValidate
          >
            {/* Title */}
            <Input
              label="Title"
              placeholder="Brief title describing the incident"
              value={form.title}
              onChange={(e) => handleFieldChange('title', e.target.value)}
              onBlur={() => handleFieldBlur('title')}
              error={errors.title}
              required
            />

            {/* Reporter Email */}
            <Input
              label="Reporter Email"
              type="email"
              placeholder="your@email.com"
              value={form.reporter_email}
              onChange={(e) => handleFieldChange('reporter_email', e.target.value)}
              onBlur={() => handleFieldBlur('reporter_email')}
              error={errors.reporter_email}
              helperText="Your email. Used to notify you when the incident is resolved."
              required
            />

            {/* Description */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-neutral-700 font-montserrat">
                Description <span className="text-semantic-error">*</span>
              </label>
              <textarea
                rows={6}
                placeholder="Describe the incident in detail: symptoms, affected systems, timeline, and impact…"
                value={form.description}
                onChange={(e) => handleFieldChange('description', e.target.value)}
                onBlur={() => handleFieldBlur('description')}
                aria-invalid={Boolean(errors.description)}
                aria-describedby={errors.description ? 'description-error' : 'description-helper'}
                className={clsx(
                  'w-full rounded-sm border px-3 py-2 text-sm text-neutral-900 font-montserrat',
                  'placeholder:text-neutral-400 resize-none',
                  'focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-brand-primary',
                  'transition-colors duration-150',
                  errors.description
                    ? 'border-semantic-error'
                    : 'border-neutral-300 hover:border-neutral-400',
                )}
              />
              {errors.description ? (
                <p
                  id="description-error"
                  role="alert"
                  className="text-sm text-semantic-error"
                >
                  {errors.description}
                </p>
              ) : (
                <p id="description-helper" className="text-xs text-neutral-400 font-montserrat">
                  {form.description.length} characters (minimum 10)
                </p>
              )}
            </div>

            {/* Log file upload */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-neutral-700 font-montserrat">
                Log File{' '}
                <span className="text-neutral-400 font-normal">(optional)</span>
              </label>
              <input
                type="file"
                accept={ACCEPTED_FILE_TYPES.join(',')}
                onChange={handleFileChange}
                className="text-sm text-neutral-700 font-montserrat file:mr-3 file:py-1.5 file:px-3 file:rounded-sm file:border-0 file:text-xs file:font-medium file:bg-brand-lighter file:text-brand-primary hover:file:bg-brand-primary hover:file:text-white file:transition-colors file:duration-150"
              />
              {logFile && !errors.logFile && (
                <p className="text-xs text-neutral-500 font-montserrat">
                  {logFile.name} ({(logFile.size / 1024).toFixed(1)} KB)
                </p>
              )}
              {errors.logFile && (
                <p role="alert" className="text-sm text-semantic-error">
                  {errors.logFile}
                </p>
              )}
              <p className="text-xs text-neutral-400 font-montserrat">
                Accepted formats: .txt, .log, .json, .csv. Maximum size: 5 MB.
              </p>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-2">
              <Button
                type="submit"
                variant="primary"
                disabled={submitDisabled}
              >
                Submit Incident
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => navigate('/incidents')}
              >
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}
    </Layout>
  )
}
