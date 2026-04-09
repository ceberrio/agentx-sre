/**
 * UsersPage — user management with role assignment.
 * Functional: calls GET /api/auth/users and PUT /api/auth/users/:id/role.
 * Role dropdown visible only to superadmin (enforced in UI, route is admin+ only).
 */
import { Users } from 'lucide-react'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { RoleBadge } from '../components/ui/Badge'
import { useUsers, useUpdateUserRole } from '../api/hooks/useAuth'
import { useAuthStore } from '../store/authStore'
import type { UserRole, UserWithStatus } from '../api/types'
import axios from 'axios'

const ALL_ROLES: UserRole[] = ['superadmin', 'admin', 'flow_configurator', 'operator', 'viewer']

const roleOptions = ALL_ROLES.map((r) => ({
  value: r,
  label: r.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
}))

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-US', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

interface UserRowProps {
  user: UserWithStatus
  isSuperAdmin: boolean
}

function UserRow({ user, isSuperAdmin }: UserRowProps) {
  const updateRole = useUpdateUserRole()

  const handleRoleChange = (newRole: string) => {
    void updateRole.mutateAsync({
      userId: user.id,
      payload: { role: newRole as UserRole },
    })
  }

  return (
    <tr className="border-t border-neutral-100 hover:bg-neutral-50 transition-colors duration-100">
      <td className="px-4 py-3">
        <div>
          <p className="text-sm font-medium text-neutral-900 font-montserrat">
            {user.email}
          </p>
          {user.full_name && (
            <p className="text-xs text-neutral-500 font-montserrat">{user.full_name}</p>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        {isSuperAdmin ? (
          <select
            value={user.role}
            onChange={(e) => handleRoleChange(e.target.value)}
            aria-label={`Change role for ${user.email}`}
            className="rounded-sm border border-neutral-300 px-2 py-1.5 text-sm text-neutral-900 font-montserrat bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-brand-primary hover:border-neutral-400 transition-colors duration-150"
          >
            {roleOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        ) : (
          <RoleBadge role={user.role} />
        )}
      </td>
      <td className="px-4 py-3">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium font-montserrat ${
            user.is_active
              ? 'bg-semantic-success-light text-green-800'
              : 'bg-neutral-100 text-neutral-500'
          }`}
        >
          {user.is_active ? 'Active' : 'Inactive'}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="text-sm text-neutral-500 font-montserrat">
          {formatDate(user.last_login_at)}
        </span>
      </td>
    </tr>
  )
}

export function UsersPage() {
  const { data, isLoading, isError, error } = useUsers()
  const currentUser = useAuthStore((s) => s.user)
  const isSuperAdmin = currentUser?.role === 'superadmin'

  return (
    <Layout pageTitle="User Management">
      <div className="flex items-center gap-3 mb-6">
        <Users size={24} className="text-brand-primary" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
            User Management
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat">
            View and manage platform users and their roles.
          </p>
        </div>
      </div>

      <Card title={`Users${data ? ` (${data.length})` : ''}`}>
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" label="Loading users..." />
          </div>
        )}

        {isError && (
          <Alert
            type="error"
            message={
              axios.isAxiosError(error)
                ? (error.response?.data?.detail as string | undefined ?? 'Failed to load users.')
                : 'Failed to load users.'
            }
          />
        )}

        {data && data.length === 0 && (
          <div className="flex items-center justify-center py-12 text-neutral-400">
            <p className="text-sm font-montserrat">No users found.</p>
          </div>
        )}

        {data && data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-neutral-500 font-montserrat">
                  <th className="px-4 py-3 font-semibold">Email / Name</th>
                  <th className="px-4 py-3 font-semibold">Role</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Last Login</th>
                </tr>
              </thead>
              <tbody>
                {data.map((user) => (
                  <UserRow key={user.id} user={user} isSuperAdmin={isSuperAdmin} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </Layout>
  )
}
