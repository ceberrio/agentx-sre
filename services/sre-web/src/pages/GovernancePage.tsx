/**
 * GovernancePage — governance thresholds and kill switch configuration.
 */
import { useState, useEffect, useCallback } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { clsx } from 'clsx'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Toggle } from '../components/ui/Toggle'
import { Alert } from '../components/ui/Alert'
import { Modal } from '../components/ui/Modal'
import { Spinner } from '../components/ui/Spinner'
import { useGovernanceThresholds, useUpdateGovernanceThresholds } from '../api/hooks/useConfig'
import type { GovernanceThresholds } from '../api/types'
import axios from 'axios'

const SEVERITY_OPTIONS = [
  { value: 'LOW', label: 'Low' },
  { value: 'MEDIUM', label: 'Medium' },
  { value: 'HIGH', label: 'High' },
  { value: 'CRITICAL', label: 'Critical' },
]

export function GovernancePage() {
  const { data, isLoading, isError, error } = useGovernanceThresholds()
  const update = useUpdateGovernanceThresholds()

  const [confidenceMin, setConfidenceMin] = useState<number>(0.7)
  const [qualityScoreMin, setQualityScoreMin] = useState<number>(0.6)
  const [severityThreshold, setSeverityThreshold] = useState<string>('HIGH')
  const [maxRagDocs, setMaxRagDocs] = useState<number>(5)
  const [killSwitchEnabled, setKillSwitchEnabled] = useState(false)
  const [confirmKillOpen, setConfirmKillOpen] = useState(false)

  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!data) return
    setConfidenceMin(data.confidence_escalation_min)
    setQualityScoreMin(data.quality_score_min_for_autoticket)
    setSeverityThreshold(data.severity_autoticket_threshold)
    setMaxRagDocs(data.max_rag_docs_to_expose)
    setKillSwitchEnabled(data.kill_switch_enabled)
  }, [data])

  const handleKillSwitchChange = useCallback((checked: boolean) => {
    if (checked) {
      setConfirmKillOpen(true)
    } else {
      setKillSwitchEnabled(false)
    }
  }, [])

  const handleConfirmKillSwitch = useCallback(() => {
    setKillSwitchEnabled(true)
    setConfirmKillOpen(false)
  }, [])

  const handleSave = useCallback(async () => {
    setSuccessMsg(null)
    setErrorMsg(null)
    const body: GovernanceThresholds = {
      confidence_escalation_min: confidenceMin,
      quality_score_min_for_autoticket: qualityScoreMin,
      severity_autoticket_threshold: severityThreshold as GovernanceThresholds['severity_autoticket_threshold'],
      max_rag_docs_to_expose: maxRagDocs,
      kill_switch_enabled: killSwitchEnabled,
    }
    try {
      await update.mutateAsync(body)
      setSuccessMsg('Governance thresholds saved successfully.')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setErrorMsg(err.response?.data?.detail as string | undefined ?? 'Failed to save configuration.')
      } else {
        setErrorMsg('An unexpected error occurred.')
      }
    }
  }, [confidenceMin, qualityScoreMin, severityThreshold, maxRagDocs, killSwitchEnabled, update])

  return (
    <Layout pageTitle="Governance & Thresholds">
      <div className="flex items-center gap-3 mb-6">
        <SlidersHorizontal size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            Governance & Thresholds
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            Configure confidence thresholds, escalation rules, and kill switch settings.
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

      <Card title="Governance Thresholds">
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
            <Input
              label="Minimum Confidence for Auto-Resolution"
              type="number"
              value={confidenceMin}
              min={0}
              max={1}
              step={0.01}
              onChange={(e) => setConfidenceMin(Number(e.target.value))}
              helperText="Incidents with confidence below this threshold are escalated. Range: 0.00–1.00."
            />

            <Input
              label="Minimum Quality Score for Auto-Ticket"
              type="number"
              value={qualityScoreMin}
              min={0}
              max={1}
              step={0.01}
              onChange={(e) => setQualityScoreMin(Number(e.target.value))}
              helperText="Minimum triage quality score required to trigger automatic ticket creation. Range: 0.00–1.00."
            />

            <Select
              label="Severity Threshold for Auto-Ticket"
              options={SEVERITY_OPTIONS}
              value={severityThreshold}
              onChange={(e) => setSeverityThreshold(e.target.value)}
              helperText="Incidents at or above this severity will trigger automatic ticket creation."
            />

            <Input
              label="Max RAG Documents Exposed to LLM"
              type="number"
              value={maxRagDocs}
              min={1}
              max={20}
              onChange={(e) => setMaxRagDocs(Number(e.target.value))}
              helperText="Maximum number of context documents retrieved and passed to the LLM. Range: 1–20."
            />

            {/* Kill Switch */}
            <div
              className={clsx(
                'rounded-md border p-4 transition-colors duration-150',
                killSwitchEnabled ? 'border-red-500 bg-red-50' : 'border-neutral-200',
              )}
            >
              <div className="flex items-start gap-3">
                <Toggle
                  checked={killSwitchEnabled}
                  onChange={handleKillSwitchChange}
                  label="Kill Switch — Disable Auto-Ticketing"
                  description="When enabled, all automatic ticket creation is suspended. All incidents will require manual review and ticketing."
                  id="kill-switch"
                />
              </div>
              {killSwitchEnabled && (
                <p className="text-sm font-semibold text-red-600 font-montserrat mt-3">
                  Auto-ticketing is currently DISABLED. Manual review required for all incidents.
                </p>
              )}
            </div>

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

      {/* Kill Switch confirmation modal */}
      <Modal
        isOpen={confirmKillOpen}
        onClose={() => setConfirmKillOpen(false)}
        title="Confirm Kill Switch Activation"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmKillOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleConfirmKillSwitch}>
              Confirm — Disable Auto-Ticketing
            </Button>
          </>
        }
      >
        <p className="text-sm text-neutral-700 font-montserrat">
          Are you sure you want to disable auto-ticketing? All incidents will require
          manual review.
        </p>
        <p className="text-sm text-neutral-500 font-montserrat mt-3">
          This setting takes effect immediately after saving.
        </p>
      </Modal>
    </Layout>
  )
}
