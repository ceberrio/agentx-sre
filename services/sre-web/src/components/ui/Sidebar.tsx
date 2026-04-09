/**
 * Sidebar — left navigation with SoftServe brand identity.
 * AC-04: logo at top. Active state: brand-lighter bg + brand-primary text + left border.
 * Role-based nav: items filtered by current user's role (ARC-022).
 * Shows user email + role badge at the bottom.
 */
import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  AlertTriangle,
  Settings,
  SlidersHorizontal,
  Bot,
  Users,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAuthStore } from '../../store/authStore'
import { RoleBadge } from './Badge'
import type { UserRole } from '../../api/types'

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  allowedRoles?: UserRole[] // undefined = any authenticated user
}

const NAV_ITEMS: NavItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: <LayoutDashboard size={20} />,
  },
  {
    label: 'Incidents',
    path: '/incidents',
    icon: <AlertTriangle size={20} />,
    allowedRoles: ['operator', 'flow_configurator', 'admin', 'superadmin'],
  },
  {
    label: 'Configuration',
    path: '/config',
    icon: <Settings size={20} />,
    allowedRoles: ['admin', 'superadmin'],
  },
  {
    label: 'Governance',
    path: '/governance',
    icon: <SlidersHorizontal size={20} />,
    allowedRoles: ['flow_configurator', 'admin', 'superadmin'],
  },
  {
    label: 'Agents',
    path: '/agents',
    icon: <Bot size={20} />,
    allowedRoles: ['flow_configurator', 'admin', 'superadmin'],
  },
  {
    label: 'Users',
    path: '/users',
    icon: <Users size={20} />,
    allowedRoles: ['admin', 'superadmin'],
  },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Filter nav items by current user's role
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (!item.allowedRoles) return true
    if (!user) return false
    return item.allowedRoles.includes(user.role)
  })

  return (
    <aside
      className={clsx(
        'flex flex-col h-screen bg-white border-r border-neutral-200 shadow-sm',
        'transition-all duration-150',
        collapsed ? 'w-16' : 'w-60',
      )}
      aria-label="Main navigation"
    >
      {/* Logo area (AC-04) */}
      <div
        className={clsx(
          'flex items-center h-16 border-b border-neutral-100 px-4',
          collapsed ? 'justify-center' : 'justify-between',
        )}
      >
        {!collapsed && (
          <img
            src="/assets/softserve-logo.svg"
            alt="SoftServe"
            className="h-7 w-auto"
          />
        )}
        {collapsed && (
          <span
            className="text-brand-primary font-bold font-montserrat text-lg"
            aria-label="SoftServe"
          >
            S
          </span>
        )}

        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="text-neutral-500 hover:text-brand-primary transition-colors duration-150 ml-auto"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Navigation items — filtered by role */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
        {visibleItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium font-montserrat',
                'transition-colors duration-150',
                isActive
                  ? 'bg-brand-lighter text-brand-primary border-l-2 border-brand-primary pl-2'
                  : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900',
              )
            }
            aria-label={collapsed ? item.label : undefined}
          >
            <span className="flex-shrink-0">{item.icon}</span>
            {!collapsed && <span className="truncate">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* User info + role badge */}
      {user && !collapsed && (
        <div className="border-t border-neutral-100 px-4 py-3">
          <p
            className="text-xs text-neutral-700 font-montserrat font-medium truncate"
            title={user.email}
          >
            {user.email}
          </p>
          <div className="mt-1">
            <RoleBadge role={user.role} />
          </div>
        </div>
      )}

      {/* Separator + Logout */}
      <div className="border-t border-neutral-100 p-2">
        <button
          type="button"
          onClick={handleLogout}
          className={clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium font-montserrat w-full',
            'text-neutral-600 hover:bg-neutral-50 hover:text-semantic-error transition-colors duration-150',
          )}
          aria-label="Logout"
        >
          <LogOut size={20} className="flex-shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </aside>
  )
}
