/**
 * Layout — main app shell combining Sidebar + TopBar + content area.
 * KillSwitchBanner is sticky at the very top of the viewport.
 */
import { type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { KillSwitchBanner } from './KillSwitchBanner'

interface LayoutProps {
  children: ReactNode
  pageTitle: string
}

export function Layout({ children, pageTitle }: LayoutProps) {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Kill switch banner — sticky above everything */}
      <KillSwitchBanner />

      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <Sidebar />

        {/* Main content area */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <TopBar title={pageTitle} />

          <main
            className="flex-1 overflow-y-auto bg-neutral-50 p-6"
            id="main-content"
            role="main"
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}
