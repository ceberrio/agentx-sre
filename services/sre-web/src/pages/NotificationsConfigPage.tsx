/**
 * NotificationsConfigPage — email and Slack notification settings.
 */
import { useState, useEffect, useCallback } from 'react'
import { Bell } from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { useNotificationsConfig, useUpdateNotificationsConfig } from '../api/hooks/useConfig'
import axios from 'axios'

const PROVIDER_OPTIONS = [
  { value: 'mock', label: 'Mock (Testing)' },
  { value: 'slack', label: 'Slack' },
  { value: 'email', label: 'Email (SMTP)' },
  { value: 'teams', label: 'Microsoft Teams' },
]

export function NotificationsConfigPage() {
  const { data, isLoading, isError, error } = useNotificationsConfig()
  const update = useUpdateNotificationsConfig()

  const [provider, setProvider] = useState<string>('mock')
  const [slackChannel, setSlackChannel] = useState('')
  const [slackBotToken, setSlackBotToken] = useState('')
  const [smtpHost, setSmtpHost] = useState('')
  const [smtpPort, setSmtpPort] = useState<number>(587)
  const [smtpUser, setSmtpUser] = useState('')
  const [smtpPassword, setSmtpPassword] = useState('')

  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!data) return
    setProvider(data.notify_provider)
    setSlackChannel(data.slack_channel ?? '')
    setSlackBotToken('')
    setSmtpHost(data.smtp_host ?? '')
    setSmtpPort(data.smtp_port ?? 587)
    setSmtpUser(data.smtp_user ?? '')
    setSmtpPassword('')
  }, [data])

  const handleSave = useCallback(async () => {
    setSuccessMsg(null)
    setErrorMsg(null)
    const body: Record<string, unknown> = { notify_provider: provider }
    if (provider === 'slack') {
      body.slack_channel = slackChannel
      if (slackBotToken) body.slack_bot_token = slackBotToken
    }
    if (provider === 'email') {
      body.smtp_host = smtpHost
      body.smtp_port = smtpPort
      body.smtp_user = smtpUser
      if (smtpPassword) body.smtp_password = smtpPassword
    }
    try {
      await update.mutateAsync(body)
      setSuccessMsg('Notifications configuration saved successfully.')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setErrorMsg(err.response?.data?.detail as string | undefined ?? 'Failed to save configuration.')
      } else {
        setErrorMsg('An unexpected error occurred.')
      }
    }
  }, [provider, slackChannel, slackBotToken, smtpHost, smtpPort, smtpUser, smtpPassword, update])

  return (
    <Layout pageTitle="Notifications Configuration">
      <div className="flex items-center gap-3 mb-6">
        <Bell size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            Notifications Configuration
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            Configure email and Slack notification channels.
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

      <Card title="Notification Channels">
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
            <Select
              label="Notification Provider"
              options={PROVIDER_OPTIONS}
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            />

            {provider === 'mock' && (
              <Alert
                type="info"
                message="Using mock notifications. No credentials needed. Notifications are logged but not delivered."
              />
            )}

            {provider === 'slack' && (
              <div className="space-y-4">
                <Input
                  label="Slack Channel"
                  type="text"
                  placeholder="#incidents"
                  value={slackChannel}
                  onChange={(e) => setSlackChannel(e.target.value)}
                  helperText="Channel name including the # prefix (e.g. #sre-alerts)."
                />
                <Input
                  label="Slack Bot Token"
                  type="password"
                  placeholder={data.slack_bot_token === null ? '••••••••  (saved — enter to replace)' : 'Enter token'}
                  value={slackBotToken}
                  onChange={(e) => setSlackBotToken(e.target.value)}
                  helperText="Bot token starting with xoxb-. Leave blank to keep the current token."
                />
              </div>
            )}

            {provider === 'email' && (
              <div className="space-y-4">
                <Input
                  label="SMTP Host"
                  type="text"
                  placeholder="smtp.gmail.com"
                  value={smtpHost}
                  onChange={(e) => setSmtpHost(e.target.value)}
                  helperText="Hostname of your SMTP server."
                />
                <Input
                  label="SMTP Port"
                  type="number"
                  placeholder="587"
                  value={smtpPort}
                  min={1}
                  max={65535}
                  onChange={(e) => setSmtpPort(Number(e.target.value))}
                  helperText="Common ports: 587 (STARTTLS), 465 (SSL), 25 (plain)."
                />
                <Input
                  label="SMTP User"
                  type="email"
                  placeholder="notifications@yourorg.com"
                  value={smtpUser}
                  onChange={(e) => setSmtpUser(e.target.value)}
                  helperText="Email address used for authentication."
                />
                <Input
                  label="SMTP Password"
                  type="password"
                  placeholder={data.smtp_password === null ? '••••••••  (saved — enter to replace)' : 'Enter password'}
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  helperText="SMTP password or app password. Leave blank to keep the current value."
                />
              </div>
            )}

            {provider === 'teams' && (
              <Alert
                type="info"
                message="Teams webhook not yet supported in this build."
              />
            )}

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
