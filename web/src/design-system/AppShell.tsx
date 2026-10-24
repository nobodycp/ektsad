import { useState, type ReactNode } from "react"

export type NavItem = { id: string; label: string; href: string }
export type NavGroup = { id: string; label: string; items: NavItem[] }
export type NavEntry = NavItem | NavGroup

export type AppShellProps = {
  title: string
  subtitle?: string
  nav: NavEntry[]
  activeId?: string
  pageTitle?: ReactNode
  tools?: ReactNode
  greeting?: ReactNode
  children: ReactNode
}

const ICONS: Record<string, string[]> = {
  overview: ["M4 11l8-7 8 7", "M6 10v9h12v-9"],
  complaints: ["M7 3h10v18H7z", "M10 8h4", "M10 12h4", "M10 16h3"],
  "field-missions": ["M8 3h8v2H8z", "M6 5h12v16H6z", "M9 10h6", "M9 14h6"],
  reports: ["M4 19V5", "M4 19h16", "M8 16v-5", "M12 16V8", "M16 16v-3"],
  publish: ["M12 16V4", "M7 9l5-5 5 5", "M5 20h14"],
  admin: ["M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7z"],
  "staff-report": ["M16 19v-1a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v1", "M10 8a3 3 0 1 0 0.01 0"],
  "governor-staff": ["M16 19v-1a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v1", "M10 8a3 3 0 1 0 0.01 0"],
  "complaints-report": ["M5 19V5h10l4 4v10z", "M15 5v4h4"],
  "governor-report": ["M5 19V5h10l4 4v10z", "M15 5v4h4"],
  prices: ["M4 7h16", "M4 12h16", "M4 17h10"],
  crossings: ["M3 16l6-6 4 4 8-8", "M14 6h7v7"],
  users: ["M16 19v-1a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v1", "M9.5 8a3 3 0 1 0 0.01 0"],
  governorates: ["M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z", "M12 10.5a1.5 1.5 0 1 0 0.01 0"],
  regions: ["M4 6h16v12H4z", "M4 10h16"],
  "system-settings": ["M12 8a4 4 0 1 0 0.01 0", "M12 2v2", "M12 20v2", "M2 12h2", "M20 12h2"],
  "telegram-settings": ["M21 5L3 11l7 2 2 7z"],
  "telegram-health": ["M4 12h4l2-5 4 10 2-5h4"],
  account: ["M12 8a4 4 0 1 0 0.01 0", "M4 20a8 8 0 0 1 16 0"],
}

function NavIcon({ id }: { id: string }) {
  return (
    <svg className="ds-nav-icon" viewBox="0 0 24 24" aria-hidden="true">
      {(ICONS[id] ?? ICONS.overview).map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  )
}

function isGroup(entry: NavEntry): entry is NavGroup {
  return "items" in entry
}

export function AppShell({ title, subtitle, nav, activeId, pageTitle, tools, greeting, children }: AppShellProps) {
  const [open, setOpen] = useState(false)
  const initiallyOpen = nav.filter(isGroup).find((group) => group.items.some((item) => item.id === activeId))?.id
  const [openGroup, setOpenGroup] = useState<string | null>(initiallyOpen ?? null)

  return (
    <div className={`ds-shell${open ? " is-nav-open" : ""}`} dir="rtl" lang="ar">
      <button className="ds-shell__backdrop" type="button" aria-label="إغلاق القائمة" onClick={() => setOpen(false)} />
      <aside className="ds-shell__sidebar" id="app-sidebar">
        <a className="ds-shell__brand" href="/overview/">
          <span className="ds-shell__mark" aria-hidden="true">
            {title.trim().slice(0, 1)}
          </span>
          <span className="ds-shell__brand-text">
            <span className="ds-shell__brand-name">{title}</span>
            {subtitle && <span className="ds-shell__brand-tag">{subtitle}</span>}
          </span>
        </a>
        <nav className="ds-shell__nav" aria-label="التنقل الرئيسي">
          {nav.map((entry) =>
            isGroup(entry) ? (
              <div key={entry.id} className={`ds-nav-group${openGroup === entry.id ? " is-open" : ""}`}>
                <button
                  type="button"
                  className="ds-nav-group__toggle"
                  aria-expanded={openGroup === entry.id}
                  onClick={() => setOpenGroup((current) => (current === entry.id ? null : entry.id))}
                >
                  <NavIcon id={entry.id} />
                  <span className="ds-nav-group__label">{entry.label}</span>
                  <span className="ds-nav-group__chevron" aria-hidden="true">
                    <svg viewBox="0 0 24 24">
                      <path d="M9 6l6 6-6 6" />
                    </svg>
                  </span>
                </button>
                <div className="ds-nav-group__panel">
                  <div className="ds-nav-group__items">
                    {entry.items.map((item) => (
                      <a
                        key={item.id}
                        className="ds-shell__link"
                        href={item.href}
                        aria-current={item.id === activeId ? "page" : undefined}
                        onClick={() => setOpen(false)}
                      >
                        <NavIcon id={item.id} />
                        {item.label}
                      </a>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <a
                key={entry.id}
                className="ds-shell__link"
                href={entry.href}
                aria-current={entry.id === activeId ? "page" : undefined}
                onClick={() => setOpen(false)}
              >
                <NavIcon id={entry.id} />
                {entry.label}
              </a>
            ),
          )}
        </nav>
      </aside>
      <div className="ds-shell__body">
        <header className="ds-shell__header">
          <div className="ds-shell__header-start">
            <button
              type="button"
              className="ds-menu-btn"
              aria-controls="app-sidebar"
              aria-expanded={open}
              aria-label="فتح القائمة"
              onClick={() => setOpen((value) => !value)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
            {greeting}
          </div>
          {tools}
        </header>
        <main className="ds-shell__main">
          {pageTitle && <h1 className="ds-shell__title">{pageTitle}</h1>}
          {children}
        </main>
      </div>
    </div>
  )
}
