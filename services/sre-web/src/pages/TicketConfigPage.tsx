/**
 * TicketConfigPage — ticketing system integration configuration.
 */
import { useState, useEffect, useCallback } from 'react'
import { Ticket } from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { useTicketSystemConfig, useUpdateTicketSystemConfig } from '../api/hooks/useConfig'
import axios from 'axios'

const PROVIDER_OPTIONS = [
  { value: 'mock', label: 'Mock (Testing)' },
  { value: 'gitlab', label: 'GitLab' },
  { value: 'jira', label: 'Jira' },
]

export function TicketConfigPage() {
  const { data, isLoading, isError, error } = useTicketSystemConfig()
  const update = useUpdateTicketSystemConfig()

  const [provider, setProvider] = useState<string>('mock')
  const [gitlabUrl, setGitlabUrl] = useState('')
  const [gitlabProjectId, setGitlabProjectId] = useState('')
  const [gitlabToken, setGitlabToken] = useState('')
  const [jiraUrl, setJiraUrl] = useState('')
  const [jiraProjectKey, setJiraProjectKey] = useState('')
  const [jiraApiToken, setJiraApiToken] = useState('')

  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!data) return
    setProvider(data.ticket_provider)
    setGitlabUrl(data.gitlab_url ?? '')
    setGitlabProjectId(data.gitlab_project_id ?? '')
    setGitlabToken('')
    setJiraUrl(data.jira_url ?? '')
    setJiraProjectKey(data.jira_project_key ?? '')
    setJiraApiToken('')
  }, [data])

  const handleSave = useCallback(async () => {
    setSuccessMsg(null)
    setErrorMsg(null)
    const body: Record<string, unknown> = { ticket_provider: provider }
    if (provider === 'gitlab') {
      body.gitlab_url = gitlabUrl
      body.gitlab_project_id = gitlabProjectId
      if (gitlabToken) body.gitlab_token = gitlabToken
    }
    if (provider === 'jira') {
      body.jira_url = jiraUrl
      body.jira_project_key = jiraProjectKey
      if (jiraApiToken) body.jira_api_token = jiraApiToken
    }
    try {
      await update.mutateAsync(body)
      setSuccessMsg('Ticket system configuration saved successfully.')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setErrorMsg(err.response?.data?.detail as string | undefined ?? 'Failed to save configuration.')
      } else {
        setErrorMsg('An unexpected error occurred.')
      }
    }
  }, [provider, gitlabUrl, gitlabProjectId, gitlabToken, jiraUrl, jiraProjectKey, jiraApiToken, update])

  return (
    <Layout pageTitle="Ticket System Configuration">
      <div className="flex items-center gap-3 mb-6">
        <Ticket size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            Ticket System Configuration
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            Connect and configure your ticketing platform integration.
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

      <Card title="Ticket System Configuration">
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
              label="Ticket Provider"
              options={PROVIDER_OPTIONS}
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            />

            {provider === 'mock' && (
              <Alert
                type="info"
                message="Using mock ticket system. No credentials needed. Tickets are simulated and not persisted."
              />
            )}

            {provider === 'gitlab' && (
              <div className="space-y-4">
                <Input
                  label="GitLab URL"
                  type="url"
                  placeholder="https://gitlab.com"
                  value={gitlabUrl}
                  onChange={(e) => setGitlabUrl(e.target.value)}
                  helperText="Base URL of your GitLab instance."
                />
                <Input
                  label="GitLab Project ID"
                  type="text"
                  placeholder="12345678"
                  value={gitlabProjectId}
                  onChange={(e) => setGitlabProjectId(e.target.value)}
                  helperText="Numeric project ID found in GitLab project settings."
                />
                <Input
                  label="GitLab Token"
                  type="password"
                  placeholder={data.gitlab_token === null ? '••••••••  (saved — enter to replace)' : 'Enter token'}
                  value={gitlabToken}
                  onChange={(e) => setGitlabToken(e.target.value)}
                  helperText="Personal access token with api scope. Leave blank to keep the current token."
                />
              </div>
            )}

            {provider === 'jira' && (
              <div className="space-y-4">
                <Input
                  label="Jira URL"
                  type="url"
                  placeholder="https://yourorg.atlassian.net"
                  value={jiraUrl}
                  onChange={(e) => setJiraUrl(e.target.value)}
                  helperText="Base URL of your Jira instance."
                />
                <Input
                  label="Jira Project Key"
                  type="text"
                  placeholder="SRE"
                  value={jiraProjectKey}
                  onChange={(e) => setJiraProjectKey(e.target.value)}
                  helperText="Project key in uppercase (e.g. SRE, OPS)."
                />
                <Input
                  label="Jira API Token"
                  type="password"
                  placeholder={data.jira_api_token === null ? '••••••••  (saved — enter to replace)' : 'Enter token'}
                  value={jiraApiToken}
                  onChange={(e) => setJiraApiToken(e.target.value)}
                  helperText="API token generated in Atlassian account settings. Leave blank to keep the current token."
                />
              </div>
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
