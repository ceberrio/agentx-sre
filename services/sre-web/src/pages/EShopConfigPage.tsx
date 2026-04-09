/**
 * EShopConfigPage — eShopOnWeb RAG integration status and context provider config.
 * Functional: calls GET /api/context/status and POST /api/context/reindex.
 * Re-index button is available to admin and superadmin only (enforced at route level).
 */
import { useState, useEffect, useCallback } from 'react'
import { ShoppingCart, RefreshCw, ExternalLink, Clock, FileText, Layers } from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'
import { Spinner } from '../components/ui/Spinner'
import { Alert } from '../components/ui/Alert'
import { Modal } from '../components/ui/Modal'
import { StatusBadge } from '../components/ui/Badge'
import { useContextStatus, useReindex } from '../api/hooks/useContext'
import { useEcommerceRepoConfig, useUpdateEcommerceRepoConfig } from '../api/hooks/useConfig'
import type { ContextProviderStatus } from '../api/types'
import axios from 'axios'

const CONTEXT_PROVIDER_OPTIONS = [
  { value: 'static', label: 'Static' },
  { value: 'faiss', label: 'FAISS' },
  { value: 'github', label: 'GitHub' },
]

function statusToDisplayStatus(status: ContextProviderStatus): 'open' | 'processing' | 'ticketed' {
  if (status === 'ready') return 'ticketed'
  if (status === 'building') return 'processing'
  return 'open' // fallback
}

function formatDate(iso: string | null): string {
  if (!iso) return 'Never'
  return new Date(iso).toLocaleString('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function EShopConfigPage() {
  const { data, isLoading, isError, error } = useContextStatus()
  const reindex = useReindex()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [reindexError, setReindexError] = useState<string | null>(null)
  const [reindexSuccess, setReindexSuccess] = useState(false)

  const { data: repoConfig, isLoading: repoLoading, isError: repoIsError } = useEcommerceRepoConfig()
  const updateRepo = useUpdateEcommerceRepoConfig()
  const [contextProvider, setContextProvider] = useState<string>('static')
  const [eshopContextDir, setEshopContextDir] = useState('')
  const [faissIndexPath, setFaissIndexPath] = useState('')
  const [repoSuccessMsg, setRepoSuccessMsg] = useState<string | null>(null)
  const [repoErrorMsg, setRepoErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!repoConfig) return
    setContextProvider(repoConfig.context_provider)
    setEshopContextDir(repoConfig.eshop_context_dir ?? '')
    setFaissIndexPath(repoConfig.faiss_index_path ?? '')
  }, [repoConfig])

  const handleSaveRepo = useCallback(async () => {
    setRepoSuccessMsg(null)
    setRepoErrorMsg(null)
    try {
      await updateRepo.mutateAsync({ context_provider: contextProvider })
      setRepoSuccessMsg('Context provider configuration saved successfully.')
      setTimeout(() => setRepoSuccessMsg(null), 3000)
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setRepoErrorMsg(err.response?.data?.detail as string | undefined ?? 'Failed to save configuration.')
      } else {
        setRepoErrorMsg('An unexpected error occurred.')
      }
    }
  }, [contextProvider, updateRepo])

  const handleReindex = async () => {
    setConfirmOpen(false)
    setReindexError(null)
    setReindexSuccess(false)
    try {
      await reindex.mutateAsync()
      setReindexSuccess(true)
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        setReindexError(err.response?.data?.detail as string | undefined ?? 'Re-index failed.')
      } else {
        setReindexError('An unexpected error occurred.')
      }
    }
  }

  return (
    <Layout pageTitle="eShop Context">
      <div className="flex items-center gap-3 mb-6">
        <ShoppingCart size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            eShop Context
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            eShopOnWeb RAG integration status and indexing control.
          </p>
        </div>
      </div>

      {reindexSuccess && (
        <div className="mb-4">
          <Alert
            type="success"
            message="Re-indexing started. Status will update when complete."
            onDismiss={() => setReindexSuccess(false)}
          />
        </div>
      )}

      {reindexError && (
        <div className="mb-4">
          <Alert
            type="error"
            message={reindexError}
            onDismiss={() => setReindexError(null)}
          />
        </div>
      )}

      <Card title="Integration Status">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" label="Loading context status..." />
          </div>
        )}

        {isError && (
          <Alert
            type="error"
            message={
              axios.isAxiosError(error)
                ? (error.response?.data?.detail as string | undefined ?? 'Failed to load context status.')
                : 'Failed to load context status.'
            }
          />
        )}

        {data && (
          <div className="space-y-6">
            {/* Status row */}
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-neutral-700 font-montserrat">
                  Status:
                </span>
                <StatusBadge status={statusToDisplayStatus(data.status)} />
                <span className="text-xs text-neutral-500 font-montserrat capitalize">
                  ({data.status})
                </span>
              </div>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => setConfirmOpen(true)}
                loading={reindex.isPending}
                className="flex items-center gap-2 ml-auto"
              >
                <RefreshCw size={14} />
                Re-index
              </Button>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-neutral-50 rounded-md p-4 flex items-start gap-3">
                <FileText size={18} className="text-brand-primary mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs text-neutral-500 font-montserrat">Indexed Files</p>
                  <p className="text-xl font-bold text-neutral-900 font-montserrat">
                    {data.indexed_files.toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="bg-neutral-50 rounded-md p-4 flex items-start gap-3">
                <Layers size={18} className="text-brand-primary mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs text-neutral-500 font-montserrat">Total Chunks</p>
                  <p className="text-xl font-bold text-neutral-900 font-montserrat">
                    {data.total_chunks.toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="bg-neutral-50 rounded-md p-4 flex items-start gap-3">
                <Clock size={18} className="text-brand-primary mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs text-neutral-500 font-montserrat">Last Indexed</p>
                  <p className="text-sm font-semibold text-neutral-900 font-montserrat">
                    {formatDate(data.last_indexed_at)}
                  </p>
                </div>
              </div>
            </div>

            {/* Repo URL */}
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-neutral-700 font-montserrat">
                Repository:
              </span>
              <a
                href={data.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-brand-primary font-montserrat hover:underline flex items-center gap-1"
              >
                {data.repo_url}
                <ExternalLink size={12} />
              </a>
            </div>
          </div>
        )}
      </Card>

      {/* Re-index confirmation modal */}
      <Modal
        isOpen={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirm Re-indexing"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => void handleReindex()}>
              Re-index Now
            </Button>
          </>
        }
      >
        <p className="text-sm text-neutral-700 font-montserrat">
          This will re-index the entire eShopOnWeb repository. The process may take
          several minutes. Existing RAG context will remain available until re-indexing
          is complete.
        </p>
        <p className="text-sm text-neutral-500 font-montserrat mt-3">
          Are you sure you want to proceed?
        </p>
      </Modal>

      {/* Context Provider Configuration */}
      <div className="mt-6">
        {repoSuccessMsg && (
          <div className="mb-4">
            <Alert type="success" message={repoSuccessMsg} onDismiss={() => setRepoSuccessMsg(null)} />
          </div>
        )}
        {repoErrorMsg && (
          <div className="mb-4">
            <Alert type="error" message={repoErrorMsg} onDismiss={() => setRepoErrorMsg(null)} />
          </div>
        )}

        <Card title="Context Provider Configuration">
          {repoLoading && (
            <div className="flex items-center justify-center py-12">
              <Spinner size="lg" label="Loading configuration..." />
            </div>
          )}

          {repoIsError && (
            <Alert type="error" message="Failed to load context provider configuration." />
          )}

          {repoConfig && (
            <div className="space-y-6">
              <Select
                label="Context Provider"
                options={CONTEXT_PROVIDER_OPTIONS}
                value={contextProvider}
                onChange={(e) => setContextProvider(e.target.value)}
                helperText="Provider used to retrieve eShop context for RAG."
              />

              <Input
                label="eShop Context Directory"
                type="text"
                value={eshopContextDir}
                onChange={(e) => setEshopContextDir(e.target.value)}
                disabled
                helperText="These paths are set at container build time and are read-only."
              />

              <Input
                label="FAISS Index Path"
                type="text"
                value={faissIndexPath}
                onChange={(e) => setFaissIndexPath(e.target.value)}
                disabled
                helperText="These paths are set at container build time and are read-only."
              />

              <div className="flex justify-end pt-2">
                <Button
                  variant="primary"
                  onClick={() => void handleSaveRepo()}
                  loading={updateRepo.isPending}
                  disabled={updateRepo.isPending}
                >
                  Save Configuration
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </Layout>
  )
}
