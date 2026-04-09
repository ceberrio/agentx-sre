/**
 * ConfigPage — configuration hub.
 * Shows cards linking to each configuration sub-section.
 * Admin and superadmin only (enforced by ProtectedRoute, not here — ARC-022).
 */
import {
  Brain,
  Ticket,
  Bell,
  ShoppingCart,
  Shield,
  Settings,
  SlidersHorizontal,
  Activity,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Layout } from '../components/ui/Layout'

interface ConfigCardProps {
  title: string
  description: string
  href: string
  icon: React.ReactNode
}

function ConfigCard({ title, description, href, icon }: ConfigCardProps) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      onClick={() => navigate(href)}
      className="bg-white rounded-lg border border-neutral-200 shadow-sm p-5 flex flex-col gap-3 text-left hover:border-brand-primary hover:shadow-md transition-all duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-primary"
    >
      <div className="w-10 h-10 rounded-md bg-brand-lighter flex items-center justify-center text-brand-primary">
        {icon}
      </div>
      <div>
        <p className="text-sm font-semibold text-neutral-900 font-montserrat">{title}</p>
        <p className="text-xs text-neutral-500 font-montserrat mt-0.5">{description}</p>
      </div>
    </button>
  )
}

export function ConfigPage() {
  return (
    <Layout pageTitle="Configuration">
      <div className="flex items-center gap-3 mb-6">
        <Settings size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            Configuration
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            System configuration modules.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        <ConfigCard
          title="LLM Provider"
          description="Configure AI model and API keys"
          href="/config/llm"
          icon={<Brain size={20} />}
        />
        <ConfigCard
          title="Ticket System"
          description="Connect your ticketing platform"
          href="/config/tickets"
          icon={<Ticket size={20} />}
        />
        <ConfigCard
          title="Notifications"
          description="Email and Slack settings"
          href="/config/notifications"
          icon={<Bell size={20} />}
        />
        <ConfigCard
          title="eShop Context"
          description="eShopOnWeb integration status"
          href="/config/eshop"
          icon={<ShoppingCart size={20} />}
        />
        <ConfigCard
          title="Security"
          description="Guardrails and upload limits"
          href="/config/security"
          icon={<Shield size={20} />}
        />
        <ConfigCard
          title="Governance & Thresholds"
          description="Confidence thresholds, escalation rules, kill switch"
          href="/governance"
          icon={<SlidersHorizontal size={20} />}
        />
        <ConfigCard
          title="Observability"
          description="Logging, Langfuse tracing, explainability"
          href="/config/observability"
          icon={<Activity size={20} />}
        />
      </div>
    </Layout>
  )
}
