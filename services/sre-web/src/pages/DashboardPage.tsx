/**
 * DashboardPage — drag-and-drop widget layout.
 * Uses @dnd-kit/core + @dnd-kit/sortable for reorderable widget cards.
 * Widget order persists in localStorage (key: sre-dashboard-layout).
 * All text in English (AC-12, BR-06).
 */
import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext,
  type DragEndEvent,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  rectSortingStrategy,
  useSortable,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  Activity,
  AlertTriangle,
  Bot,
  GripVertical,
  CheckCircle,
} from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { StatusBadge } from '../components/ui/Badge'
import { Spinner } from '../components/ui/Spinner'
import { useConfigStore } from '../store/configStore'
import { useIncidents } from '../api/hooks/useIncidents'
import { useLLMConfig } from '../api/hooks/useConfig'
import type { Incident } from '../api/types'

// ---- Widget definitions ----

type WidgetId = 'incident-summary' | 'system-status' | 'recent-incidents' | 'agent-health'

interface WidgetDef {
  id: WidgetId
  title: string
}

const WIDGET_DEFS: WidgetDef[] = [
  { id: 'incident-summary', title: 'Incident Summary' },
  { id: 'system-status', title: 'System Status' },
  { id: 'recent-incidents', title: 'Recent Incidents' },
  { id: 'agent-health', title: 'Agent Health' },
]

const LAYOUT_STORAGE_KEY = 'sre-dashboard-layout'

function loadWidgetOrder(): WidgetId[] {
  try {
    const raw = localStorage.getItem(LAYOUT_STORAGE_KEY)
    if (!raw) return WIDGET_DEFS.map((w) => w.id)
    const parsed = JSON.parse(raw) as WidgetId[]
    // Validate all IDs are still valid
    const validIds = new Set(WIDGET_DEFS.map((w) => w.id))
    if (parsed.every((id) => validIds.has(id)) && parsed.length === WIDGET_DEFS.length) {
      return parsed
    }
  } catch {
    // ignore corrupt storage
  }
  return WIDGET_DEFS.map((w) => w.id)
}

function saveWidgetOrder(order: WidgetId[]) {
  localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(order))
}

// ---- Individual widget content ----

interface IncidentSummaryProps {
  incidents: Incident[] | undefined
  isLoading: boolean
}

function IncidentSummaryContent({ incidents, isLoading }: IncidentSummaryProps) {
  const total = isLoading || !incidents ? '—' : String(incidents.length)
  const open = isLoading || !incidents ? '—' : String(incidents.filter((i) => i.status !== 'resolved').length)
  const resolved = isLoading || !incidents ? '—' : String(incidents.filter((i) => i.status === 'resolved').length)

  return (
    <div className="grid grid-cols-3 gap-4">
      {[
        { label: 'Total', value: total, icon: <Activity size={18} className="text-brand-primary" /> },
        { label: 'Open', value: open, icon: <AlertTriangle size={18} className="text-semantic-warning" /> },
        { label: 'Resolved', value: resolved, icon: <CheckCircle size={18} className="text-semantic-success" /> },
      ].map(({ label, value, icon }) => (
        <div key={label} className="flex flex-col items-center gap-1 py-2">
          {icon}
          <p className="text-2xl font-bold text-neutral-900 font-montserrat">{value}</p>
          <p className="text-xs text-neutral-500 font-montserrat">{label}</p>
        </div>
      ))}
    </div>
  )
}

interface SystemStatusProps {
  llmProvider: string | undefined
  llmLoading: boolean
}

function SystemStatusContent({ llmProvider, llmLoading }: SystemStatusProps) {
  const killSwitchEnabled = useConfigStore((s) => s.killSwitchEnabled)
  const providerLabel = llmLoading ? '—' : (llmProvider ?? '—')
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-neutral-600 font-montserrat">Kill Switch</span>
        <StatusBadge status={killSwitchEnabled ? 'error' : 'ticketed'} />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-sm text-neutral-600 font-montserrat">LLM Provider</span>
        <span className="text-sm font-medium text-neutral-700 font-montserrat">{providerLabel}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-sm text-neutral-600 font-montserrat">RAG Context</span>
        <StatusBadge status="ticketed" />
      </div>
    </div>
  )
}

interface RecentIncidentsProps {
  incidents: Incident[] | undefined
  isLoading: boolean
}

function formatIncidentDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function RecentIncidentsContent({ incidents, isLoading }: RecentIncidentsProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Spinner size="sm" label="Loading..." />
      </div>
    )
  }

  if (!incidents || incidents.length === 0) {
    return (
      <div className="flex items-center justify-center py-6 text-neutral-400">
        <p className="text-sm font-montserrat">No recent incidents.</p>
      </div>
    )
  }

  const recent = [...incidents]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)

  return (
    <div className="space-y-2">
      {recent.map((incident) => (
        <button
          key={incident.id}
          type="button"
          onClick={() => navigate('/incidents/' + incident.id)}
          className="w-full flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-neutral-50 transition-colors text-left"
        >
          <span className="text-sm text-neutral-700 font-montserrat flex-1 truncate">{incident.title}</span>
          <StatusBadge status={incident.status} />
          <span className="text-xs text-neutral-400 font-montserrat whitespace-nowrap">
            {formatIncidentDate(incident.created_at)}
          </span>
        </button>
      ))}
    </div>
  )
}

const AGENT_LIST = [
  'Intake Agent',
  'Triage Agent',
  'Ticket Agent',
  'Notification Agent',
]

function AgentHealthContent() {
  return (
    <div className="space-y-2">
      {AGENT_LIST.map((name) => (
        <div key={name} className="flex items-center gap-3">
          <Bot size={16} className="text-neutral-400 flex-shrink-0" />
          <span className="text-sm text-neutral-700 font-montserrat flex-1">{name}</span>
          <div className="flex items-center gap-1.5">
            <CheckCircle size={14} className="text-semantic-success" />
            <span className="text-xs text-semantic-success font-montserrat">OK</span>
          </div>
        </div>
      ))}
    </div>
  )
}

interface WidgetDataProps {
  incidents: Incident[] | undefined
  incidentsLoading: boolean
  llmProvider: string | undefined
  llmLoading: boolean
}

function widgetContent(id: WidgetId, data: WidgetDataProps) {
  switch (id) {
    case 'incident-summary':
      return <IncidentSummaryContent incidents={data.incidents} isLoading={data.incidentsLoading} />
    case 'system-status':
      return <SystemStatusContent llmProvider={data.llmProvider} llmLoading={data.llmLoading} />
    case 'recent-incidents':
      return <RecentIncidentsContent incidents={data.incidents} isLoading={data.incidentsLoading} />
    case 'agent-health':
      return <AgentHealthContent />
    default:
      // TypeScript exhaustive check — this branch is never reached at runtime
      throw new Error(`Unknown widget id: ${String(id)}`)
  }
}

// ---- Sortable widget card ----

interface SortableWidgetProps {
  def: WidgetDef
  widgetData: WidgetDataProps
}

function SortableWidget({ def, widgetData }: SortableWidgetProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: def.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`${isDragging ? 'opacity-50 ring-2 ring-brand-primary rounded-md' : ''}`}
    >
      <Card
        title={def.title}
        action={
          <button
            type="button"
            {...attributes}
            {...listeners}
            aria-label={`Drag ${def.title} widget`}
            className="cursor-grab active:cursor-grabbing text-neutral-400 hover:text-neutral-600 transition-colors duration-100 p-1 rounded"
          >
            <GripVertical size={16} />
          </button>
        }
      >
        {widgetContent(def.id, widgetData)}
      </Card>
    </div>
  )
}

// ---- Dashboard page ----

export function DashboardPage() {
  const [widgetOrder, setWidgetOrder] = useState<WidgetId[]>(loadWidgetOrder)

  // Fetch shared data once — passed as props to avoid duplicate fetches across widgets
  const { data: incidentsData, isLoading: incidentsLoading } = useIncidents()
  const { data: llmData, isLoading: llmLoading } = useLLMConfig()

  const widgetData: WidgetDataProps = {
    incidents: incidentsData,
    incidentsLoading,
    llmProvider: llmData?.config?.provider,
    llmLoading,
  }

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    setWidgetOrder((prev) => {
      const oldIndex = prev.indexOf(active.id as WidgetId)
      const newIndex = prev.indexOf(over.id as WidgetId)
      const next = arrayMove(prev, oldIndex, newIndex)
      saveWidgetOrder(next)
      return next
    })
  }, [])

  const orderedDefs = widgetOrder.map(
    (id) => WIDGET_DEFS.find((w) => w.id === id)!,
  )

  return (
    <Layout pageTitle="Dashboard">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={widgetOrder} strategy={rectSortingStrategy}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {orderedDefs.map((def) => (
              <SortableWidget key={def.id} def={def} widgetData={widgetData} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </Layout>
  )
}
