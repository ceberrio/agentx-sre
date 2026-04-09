/**
 * AgentsPage — agent configuration and health monitoring.
 * Stub: full implementation in a future HU.
 */
import { Bot } from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'

const AGENT_NAMES = [
  'Intake Agent',
  'Triage Agent',
  'Ticket Agent',
  'Notification Agent',
]

export function AgentsPage() {
  return (
    <Layout pageTitle="Agent Configuration">
      <div className="flex items-center gap-3 mb-6">
        <Bot size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            Agent Configuration
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            Monitor and configure the 4 SRE triage agents.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {AGENT_NAMES.map((name) => (
          <Card key={name} title={name}>
            <div className="flex items-center gap-2 py-4">
              <span className="w-2.5 h-2.5 rounded-full bg-semantic-success flex-shrink-0" />
              <span className="text-sm text-neutral-600 font-montserrat">Operational</span>
              <span className="text-xs text-neutral-400 font-montserrat ml-auto">
                Full config in next HU
              </span>
            </div>
          </Card>
        ))}
      </div>
    </Layout>
  )
}
