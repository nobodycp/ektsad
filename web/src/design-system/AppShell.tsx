import type { ReactNode } from "react"

export type NavItem = { id: string; label: string; href: string }

export type AppShellProps = {
  title: string
  subtitle?: string
  nav: NavItem[]
  activeId?: string
  headerActions?: ReactNode
  pageTitle?: ReactNode
  children: ReactNode
}

export function AppShell({ title, subtitle, nav, activeId, headerActions, pageTitle, children }: AppShellProps) {
  return (
    <div className="ds-shell" dir="rtl" lang="ar">
      <aside className="ds-shell__sidebar">
        <div className="ds-shell__brand">
          {title}
          {subtitle && <small>{subtitle}</small>}
        </div>
        <nav aria-label="التنقل الرئيسي">
          <ul className="ds-shell__nav">
            {nav.map((item) => (
              <li key={item.id}>
                <a
                  className="ds-shell__link"
                  href={item.href}
                  aria-current={item.id === activeId ? "page" : undefined}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="ds-shell__body">
        {(pageTitle || headerActions) && (
          <header className="ds-shell__header">
            {pageTitle && <h1 className="ds-shell__title">{pageTitle}</h1>}
            {headerActions}
          </header>
        )}
        <main className="ds-shell__main">{children}</main>
      </div>
    </div>
  )
}
