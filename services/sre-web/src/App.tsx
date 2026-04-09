/**
 * App — root router with full role-based protected route map.
 * Role protection is enforced exclusively by ProtectedRoute (ARC-022).
 * All text in English.
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import type { UserRole } from './api/types'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { IncidentListPage } from './pages/IncidentListPage'
import { NewIncidentPage } from './pages/NewIncidentPage'
import { IncidentDetailPage } from './pages/IncidentDetailPage'
import { ConfigPage } from './pages/ConfigPage'
import { LLMConfigPage } from './pages/LLMConfigPage'
import { TicketConfigPage } from './pages/TicketConfigPage'
import { NotificationsConfigPage } from './pages/NotificationsConfigPage'
import { EShopConfigPage } from './pages/EShopConfigPage'
import { SecurityConfigPage } from './pages/SecurityConfigPage'
import { GovernancePage } from './pages/GovernancePage'
import { ObservabilityConfigPage } from './pages/ObservabilityConfigPage'
import { AgentsPage } from './pages/AgentsPage'
import { UsersPage } from './pages/UsersPage'

const INCIDENT_ROLES: UserRole[] = ['operator', 'flow_configurator', 'admin', 'superadmin']

export function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />

      {/* Default: redirect to dashboard */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Dashboard — any authenticated user */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />

      {/* Incidents — operator, flow_configurator, admin, superadmin */}
      <Route
        path="/incidents"
        element={
          <ProtectedRoute allowedRoles={INCIDENT_ROLES}>
            <IncidentListPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/incidents/new"
        element={
          <ProtectedRoute allowedRoles={INCIDENT_ROLES}>
            <NewIncidentPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/incidents/:id"
        element={
          <ProtectedRoute allowedRoles={INCIDENT_ROLES}>
            <IncidentDetailPage />
          </ProtectedRoute>
        }
      />

      {/* Configuration hub — admin, superadmin */}
      <Route
        path="/config"
        element={
          <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
            <ConfigPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/llm"
        element={
          <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
            <LLMConfigPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/tickets"
        element={
          <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
            <TicketConfigPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/notifications"
        element={
          <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
            <NotificationsConfigPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/eshop"
        element={
          <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
            <EShopConfigPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config/security"
        element={
          <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
            <SecurityConfigPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/config/observability"
        element={
          <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
            <ObservabilityConfigPage />
          </ProtectedRoute>
        }
      />

      {/* Governance — flow_configurator, admin, superadmin */}
      <Route
        path="/governance"
        element={
          <ProtectedRoute allowedRoles={['flow_configurator', 'admin', 'superadmin']}>
            <GovernancePage />
          </ProtectedRoute>
        }
      />

      {/* Agents — flow_configurator, admin, superadmin */}
      <Route
        path="/agents"
        element={
          <ProtectedRoute allowedRoles={['flow_configurator', 'admin', 'superadmin']}>
            <AgentsPage />
          </ProtectedRoute>
        }
      />

      {/* User Management — admin, superadmin */}
      <Route
        path="/users"
        element={
          <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
            <UsersPage />
          </ProtectedRoute>
        }
      />

      {/* 404 catch-all */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
