/**
 * SecurityConfigPage — guardrails and upload limits configuration.
 */
import { useState, useEffect, useCallback } from 'react'
import { Shield } from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Toggle } from '../components/ui/Toggle'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { useSecurityConfig, useUpdateSecurityConfig } from '../api/hooks/useConfig'
import axios from 'axios'

export function SecurityConfigPage() {
  const { data, isLoading, isError, error } = useSecurityConfig()
  const update = useUpdateSecurityConfig()

  const [guardrailsEnabled, setGuardrailsEnabled] = useState(false)
  const [maxUploadSizeMb, setMaxUploadSizeMb] = useState<number>(10)

  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!data) return
    setGuardrailsEnabled(data.guardrails_llm_judge_enabled)
    setMaxUploadSizeMb(data.max_upload_size_mb)
  }, [data])

  const handleSave = useCallback(async () => {
    setSuccessMsg(null)
    setErrorMsg(null)
    try {
      await update.mutateAsync({
        guardrails_llm_judge_enabled: guardrailsEnabled,
        max_upload_size_mb: maxUploadSizeMb,
      })
      setSuccessMsg('Security configuration saved successfully.')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setErrorMsg(err.response?.data?.detail as string | undefined ?? 'Failed to save configuration.')
      } else {
        setErrorMsg('An unexpected error occurred.')
      }
    }
  }, [guardrailsEnabled, maxUploadSizeMb, update])

  return (
    <Layout pageTitle="Security Configuration">
      <div className="flex items-center gap-3 mb-6">
        <Shield size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            Security Configuration
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            Configure guardrails, upload limits, and security policies.
          </p>
        </div>
      </div>

      {successMsg && (
        <div className="mb-4">
          <Alert type="success" message={successMsg} onDismiss={() => setSuccessMsg(null)} />
        </div>
      )}
      {errorMsg && (
        <div className="mb-4">
          <Alert type="error" message={errorMsg} onDismiss={() => setErrorMsg(null)} />
        </div>
      )}

      <Card title="Security Configuration">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" label="Loading configuration..." />
          </div>
        )}

        {isError && (
          <Alert
            type="error"
            message={
              axios.isAxiosError(error)
                ? (error.response?.data?.detail as string | undefined ?? 'Failed to load configuration.')
                : 'Failed to load configuration.'
            }
          />
        )}

        {data && (
          <div className="space-y-6">
            <Toggle
              checked={guardrailsEnabled}
              onChange={setGuardrailsEnabled}
              label="Enable LLM Judge for Guardrails"
              description="When enabled, a secondary LLM call validates agent output before returning results. Disabling reduces latency at the cost of safety."
            />

            <Input
              label="Maximum File Upload Size (MB)"
              type="number"
              value={maxUploadSizeMb}
              min={1}
              max={50}
              onChange={(e) => setMaxUploadSizeMb(Number(e.target.value))}
              helperText="Maximum size of files that can be attached to an incident report. Range: 1–50 MB."
            />

            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                onClick={() => void handleSave()}
                loading={update.isPending}
                disabled={update.isPending}
              >
                Save Configuration
              </Button>
            </div>
          </div>
        )}
      </Card>
    </Layout>
  )
}
