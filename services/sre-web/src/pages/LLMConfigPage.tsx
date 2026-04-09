/**
 * LLMConfigPage — LLM provider, API keys, model names, and circuit breaker configuration.
 */
import { useState, useEffect, useCallback } from 'react'
import { Brain } from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { useLLMConfig, useUpdateLLMConfig } from '../api/hooks/useConfig'
import { getApiErrorDetail } from '../api/errors'

const PROVIDER_OPTIONS = [
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'stub', label: 'Stub (Testing)' },
]

const FALLBACK_PROVIDER_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'stub', label: 'Stub (Testing)' },
]

// CR-010: predefined model options per provider. Providers not listed use free-text input.
const MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5 (fast, efficient)' },
    { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6 (balanced)' },
    { value: 'claude-opus-4-6', label: 'Claude Opus 4.6 (most capable)' },
  ],
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o (most capable)' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini (fast, efficient)' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
  ],
  gemini: [
    { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (fast)' },
    { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (balanced)' },
  ],
}

function getModelHelperText(prov: string): string {
  switch (prov) {
    case 'azure_openai': return 'e.g. gpt-4o'
    case 'openrouter': return 'e.g. mistralai/mistral-7b-instruct'
    case 'stub': return 'e.g. stub-model'
    default: return 'Model name as recognized by the provider API.'
  }
}

export function LLMConfigPage() {
  const { data, isLoading, isError, error } = useLLMConfig()
  const update = useUpdateLLMConfig()

  const [provider, setProvider] = useState('gemini')
  const [fallbackProvider, setFallbackProvider] = useState('none')
  const [model, setModel] = useState('')
  const [fallbackModel, setFallbackModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [fallbackApiKey, setFallbackApiKey] = useState('')
  const [cbThreshold, setCbThreshold] = useState<number>(5)
  const [cbCooldown, setCbCooldown] = useState<number>(60)
  const [timeoutS, setTimeoutS] = useState<number>(30)

  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [warnMsg, setWarnMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // CR-007: cleanup-safe auto-dismiss for success banner
  useEffect(() => {
    if (!successMsg) return
    const timer = setTimeout(() => setSuccessMsg(null), 4000)
    return () => clearTimeout(timer)
  }, [successMsg])

  useEffect(() => {
    if (!data) return
    const cfg = data.config
    setProvider(cfg.provider ?? 'gemini')
    setFallbackProvider(cfg.fallback_provider ?? 'none')
    setModel(cfg.model ?? '')
    setFallbackModel(cfg.fallback_model ?? '')
    setApiKey('')
    setFallbackApiKey('')
    setCbThreshold(cfg.circuit_breaker_threshold ?? 5)
    setCbCooldown(cfg.circuit_breaker_cooldown_s ?? 60)
    setTimeoutS(cfg.timeout_s ?? 30)
  }, [data])

  // CR-010: auto-select first model when primary provider changes to one with predefined options
  const handleProviderChange = useCallback((newProvider: string) => {
    setProvider(newProvider)
    const options = MODEL_OPTIONS[newProvider]
    if (options && options.length > 0) {
      setModel(options[0].value)
    } else {
      setModel('')
    }
  }, [])

  // CR-010: auto-select first model when fallback provider changes to one with predefined options
  const handleFallbackProviderChange = useCallback((newProvider: string) => {
    setFallbackProvider(newProvider)
    const options = MODEL_OPTIONS[newProvider]
    if (options && options.length > 0) {
      setFallbackModel(options[0].value)
    } else {
      setFallbackModel('')
    }
  }, [])

  const handleSave = useCallback(async () => {
    setSuccessMsg(null)
    setWarnMsg(null)
    setErrorMsg(null)
    const body: Record<string, unknown> = {
      provider,
      fallback_provider: fallbackProvider,
      model,
      fallback_model: fallbackModel,
      circuit_breaker_threshold: cbThreshold,
      circuit_breaker_cooldown_s: cbCooldown,
      timeout_s: timeoutS,
    }
    if (apiKey) body.api_key = apiKey
    if (fallbackApiKey) body.fallback_api_key = fallbackApiKey

    try {
      const result = await update.mutateAsync(body)
      if (result.reload_status === 'failed') {
        setWarnMsg(
          `Configuration saved, but LLM reload failed. ${result.message} (${result.elapsed_ms}ms)`
        )
      } else {
        setSuccessMsg(
          `Configuration saved and LLM reloaded successfully. (${result.elapsed_ms}ms)`
        )
      }
    } catch (err: unknown) {
      setErrorMsg(getApiErrorDetail(err, 'Failed to save configuration.'))
    }
  }, [provider, fallbackProvider, model, fallbackModel, apiKey, fallbackApiKey, cbThreshold, cbCooldown, timeoutS, update])

  const apiKeyPlaceholder = data?.config.api_key
    ? '••••••••  (saved — enter to replace)'
    : 'Enter API key'

  const fallbackApiKeyPlaceholder = data?.config.fallback_api_key
    ? '••••••••  (saved — enter to replace)'
    : 'Enter API key'

  return (
    <Layout pageTitle="LLM Provider Configuration">
      <div className="flex items-center gap-3 mb-6">
        <Brain size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            LLM Provider Configuration
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            Configure the AI model provider, API keys, and generation parameters.
          </p>
        </div>
      </div>

      {successMsg && (
        <div className="mb-4">
          <Alert type="success" message={successMsg} onDismiss={() => setSuccessMsg(null)} />
        </div>
      )}
      {warnMsg && (
        <div className="mb-4">
          <Alert type="warning" message={warnMsg} onDismiss={() => setWarnMsg(null)} />
        </div>
      )}
      {errorMsg && (
        <div className="mb-4">
          <Alert type="error" message={errorMsg} onDismiss={() => setErrorMsg(null)} />
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Spinner size="lg" label="Loading configuration..." />
        </div>
      )}

      {isError && (
        <Alert
          type="error"
          message={getApiErrorDetail(error, 'Failed to load configuration.')}
        />
      )}

      {data && (
        <div className="space-y-6">
          <Card
            title="LLM Provider Configuration"
            action={
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium font-montserrat ${
                  data.connection_ok
                    ? 'bg-semantic-success-light text-green-800'
                    : 'bg-semantic-error-light text-red-800'
                }`}
              >
                {data.connection_ok ? 'DB Connected' : 'DB Unreachable'}
              </span>
            }
          >
            <div className="space-y-4">
              <Select
                label="Primary Provider"
                options={PROVIDER_OPTIONS}
                value={provider}
                onChange={(e) => handleProviderChange(e.target.value)}
              />
              {/* CR-010: dropdown for providers with predefined models, free text otherwise */}
              {MODEL_OPTIONS[provider]?.length > 0 ? (
                <Select
                  label="Primary Model"
                  options={MODEL_OPTIONS[provider]}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  helperText="Select the model for the primary provider."
                />
              ) : (
                <Input
                  label="Primary Model"
                  type="text"
                  placeholder={getModelHelperText(provider)}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  helperText={getModelHelperText(provider)}
                />
              )}
              <Input
                label="Primary API Key"
                type="password"
                placeholder={apiKeyPlaceholder}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                helperText="API key for the primary provider. Leave blank to keep the current key."
              />

              <div className="border-t border-neutral-200 pt-4 mt-4">
                <Select
                  label="Fallback Provider"
                  options={FALLBACK_PROVIDER_OPTIONS}
                  value={fallbackProvider}
                  onChange={(e) => handleFallbackProviderChange(e.target.value)}
                  helperText="Provider used when the primary provider fails or circuit breaker trips."
                />
              </div>
              {fallbackProvider && fallbackProvider !== 'none' && (
                <>
                  {/* CR-010: dropdown for fallback provider with predefined models */}
                  {MODEL_OPTIONS[fallbackProvider]?.length > 0 ? (
                    <Select
                      label="Fallback Model"
                      options={MODEL_OPTIONS[fallbackProvider]}
                      value={fallbackModel}
                      onChange={(e) => setFallbackModel(e.target.value)}
                      helperText="Select the model for the fallback provider."
                    />
                  ) : (
                    <Input
                      label="Fallback Model"
                      type="text"
                      placeholder={getModelHelperText(fallbackProvider)}
                      value={fallbackModel}
                      onChange={(e) => setFallbackModel(e.target.value)}
                      helperText={getModelHelperText(fallbackProvider)}
                    />
                  )}
                  <Input
                    label="Fallback API Key"
                    type="password"
                    placeholder={fallbackApiKeyPlaceholder}
                    value={fallbackApiKey}
                    onChange={(e) => setFallbackApiKey(e.target.value)}
                    helperText="API key for the fallback provider. Leave blank to keep the current key."
                  />
                </>
              )}
            </div>
          </Card>

          <Card title="Circuit Breaker">
            <div className="space-y-4">
              <Input
                label="Failure Threshold"
                type="number"
                value={cbThreshold}
                min={1}
                max={20}
                onChange={(e) => setCbThreshold(Number(e.target.value))}
                helperText="Number of consecutive failures before the circuit breaker opens. Range: 1–20."
              />
              <Input
                label="Cooldown Period (seconds)"
                type="number"
                value={cbCooldown}
                min={10}
                max={600}
                onChange={(e) => setCbCooldown(Number(e.target.value))}
                helperText="Time in seconds to wait before resetting the circuit breaker. Range: 10–600."
              />
              <Input
                label="Request Timeout (seconds)"
                type="number"
                value={timeoutS}
                min={5}
                max={120}
                onChange={(e) => setTimeoutS(Number(e.target.value))}
                helperText="Maximum time to wait for an LLM response before timing out. Range: 5–120."
              />
            </div>
          </Card>

          <div className="flex justify-end">
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
    </Layout>
  )
}
