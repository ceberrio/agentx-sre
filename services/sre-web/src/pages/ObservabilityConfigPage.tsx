/**
 * ObservabilityConfigPage — log level, Langfuse, governance cache, and explainability configuration.
 */
import { useState, useEffect, useCallback } from 'react'
import { Activity } from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Toggle } from '../components/ui/Toggle'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { useObservabilityConfig, useUpdateObservabilityConfig } from '../api/hooks/useConfig'
import type { ObservabilityConfig } from '../api/types'
import axios from 'axios'

const LOG_LEVEL_OPTIONS = [
  { value: 'DEBUG', label: 'DEBUG' },
  { value: 'INFO', label: 'INFO' },
  { value: 'WARNING', label: 'WARNING' },
  { value: 'ERROR', label: 'ERROR' },
]

const EXPLAINABILITY_OPTIONS = [
  { value: 'langfuse', label: 'Langfuse' },
  { value: 'local', label: 'Local' },
  { value: 'none', label: 'None' },
]

export function ObservabilityConfigPage() {
  const { data, isLoading, isError, error } = useObservabilityConfig()
  const update = useUpdateObservabilityConfig()

  const [langfuseEnabled, setLangfuseEnabled] = useState(false)
  const [logLevel, setLogLevel] = useState<ObservabilityConfig['log_level']>('INFO')
  const [cacheTtl, setCacheTtl] = useState<number>(60)
  const [explainabilityProvider, setExplainabilityProvider] = useState<ObservabilityConfig['explainability_provider']>('none')

  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!data) return
    setLangfuseEnabled(data.langfuse_enabled)
    setLogLevel(data.log_level)
    setCacheTtl(data.governance_cache_ttl_s)
    setExplainabilityProvider(data.explainability_provider)
  }, [data])

  const handleSave = useCallback(async () => {
    setSuccessMsg(null)
    setErrorMsg(null)
    try {
      await update.mutateAsync({
        langfuse_enabled: langfuseEnabled,
        log_level: logLevel,
        governance_cache_ttl_s: cacheTtl,
        explainability_provider: explainabilityProvider,
      })
      setSuccessMsg('Observability configuration saved successfully.')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setErrorMsg(err.response?.data?.detail as string | undefined ?? 'Failed to save configuration.')
      } else {
        setErrorMsg('An unexpected error occurred.')
      }
    }
  }, [langfuseEnabled, logLevel, cacheTtl, explainabilityProvider, update])

  return (
    <Layout pageTitle="Observability Configuration">
      <div className="flex items-center gap-3 mb-6">
        <Activity size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            Observability Configuration
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            Configure logging, tracing, and explainability settings.
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

      <Card title="Observability Configuration">
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
            <Alert
              type="info"
              message="Langfuse connection keys (host, public key, secret key) are set at container startup via environment variables and are not configurable from the UI."
            />

            <Toggle
              checked={langfuseEnabled}
              onChange={setLangfuseEnabled}
              label="Enable Langfuse Tracing"
              description="When enabled, all LLM traces are sent to Langfuse for monitoring and evaluation."
            />

            <Select
              label="Log Level"
              options={LOG_LEVEL_OPTIONS}
              value={logLevel}
              onChange={(e) => setLogLevel(e.target.value as ObservabilityConfig['log_level'])}
              helperText="Minimum log level emitted by the SRE agent service."
            />

            <Input
              label="Governance Cache TTL (seconds)"
              type="number"
              value={cacheTtl}
              min={0}
              max={300}
              onChange={(e) => setCacheTtl(Number(e.target.value))}
              helperText="How long governance threshold responses are cached. Set to 0 to disable caching. Range: 0–300."
            />

            <Select
              label="Explainability Provider"
              options={EXPLAINABILITY_OPTIONS}
              value={explainabilityProvider}
              onChange={(e) => setExplainabilityProvider(e.target.value as ObservabilityConfig['explainability_provider'])}
              helperText="Provider used to generate RAG attribution and reasoning explanations."
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
