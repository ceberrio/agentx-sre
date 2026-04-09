/**
 * TopBar — page header with title, user info, role badge, and notification bell.
 */
import { Bell } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { RoleBadge } from './Badge'

interface TopBarProps {
  title: string
}

export function TopBar({ title }: TopBarProps) {
  const user = useAuthStore((s) => s.user)

  const initials = user?.email
    ? user.email.substring(0, 2).toUpperCase()
    : '??'

  return (
    <header className="h-16 bg-white border-b border-neutral-200 flex items-center justify-between px-6">
      {/* Page title */}
      <h1 className="text-xl font-semibold text-neutral-900 font-montserrat">
        {title}
      </h1>

      <div className="flex items-center gap-4">
        {/* Notification bell — placeholder */}
        <button
          type="button"
          aria-label="Notifications"
          className="relative text-neutral-500 hover:text-brand-primary transition-colors duration-150"
        >
          <Bell size={20} />
        </button>

        {/* User info */}
        {user && (
          <div className="flex items-center gap-3">
            <RoleBadge role={user.role} />
            <div className="flex items-center gap-2">
              {/* Avatar */}
              <div
                className="w-8 h-8 rounded-full bg-brand-primary flex items-center justify-center text-white text-xs font-bold font-montserrat"
                aria-label={user.email}
              >
                {initials}
              </div>
              <span className="text-sm text-neutral-700 font-montserrat hidden md:block">
                {user.email}
              </span>
            </div>
          </div>
        )}
      </div>
    </header>
  )
}
