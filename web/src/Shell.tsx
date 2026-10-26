import { useCallback, useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { AppShell, Button, type NavEntry } from "./design-system"
import { apiRequest, errorDetail, type ComplaintRow, type SessionUser } from "./api"
import { useAuth } from "./auth"
import { LOGIN_PATH, navEntries } from "./routes"
import { formatDateTime } from "./pages/common"

export const ROLE_LABELS: Record<SessionUser["role"], string> = {
  admin: "مدير النظام",
  governor: "محافظ",
  inspector: "مفتش",
  legal: "الشؤون القانونية",
  custom: "دور مخصص",
}

function internalHref(event: MouseEvent<HTMLElement>): string | null {
  if (event.defaultPrevented || event.button !== 0) return null
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null
  const anchor = (event.target as Element).closest?.("a")
  if (!anchor || anchor.target || anchor.hasAttribute("download")) return null
  const href = anchor.getAttribute("href")
  if (!href || !href.startsWith("/") || href.startsWith("//")) return null
  return href
}

function useAway(open: boolean, close: () => void) {
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target
      if (target instanceof Node && root.current?.contains(target)) return
      close()
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close()
    }
    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open, close])
  return root
}

function greeting(name: string) {
  const hour = new Date().getHours()
  const hello = hour < 12 ? "صباح الخير" : hour < 18 ? "نهارك سعيد" : "مساء الخير"
  const date = new Intl.DateTimeFormat("ar", { weekday: "long", day: "numeric", month: "long" }).format(new Date())
  return { hello: `${hello}، ${name}`, date }
}

function Notifications() {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  const root = useAway(open, close)
  const [rows, setRows] = useState<ComplaintRow[]>([])
  const [count, setCount] = useState(0)
  const [loaded, setLoaded] = useState(false)

  const load = () => {
    apiRequest<{ count: number; results: ComplaintRow[] }>("/api/complaints/notices/").then((result) => {
      if (!result.ok || !result.data) return
      setCount(result.data.count)
      setRows(result.data.results)
      setLoaded(true)
    })
  }

  useEffect(() => {
    load()
    const soon = window.setTimeout(load, 800)
    const timer = window.setInterval(load, 15000)
    window.addEventListener("focus", load)
    return () => {
      window.clearTimeout(soon)
      window.clearInterval(timer)
      window.removeEventListener("focus", load)
    }
  }, [location.pathname])

  return (
    <div className="ds-popover" ref={root}>
      <button
        type="button"
        className={count > 0 ? "ds-icon-btn is-active" : "ds-icon-btn"}
        aria-label="الإشعارات"
        aria-expanded={open}
        onClick={() => {
          setOpen((value) => !value)
          load()
        }}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 9a6 6 0 1 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9" />
          <path d="M10 20a2 2 0 0 0 4 0" />
        </svg>
        {count > 0 && <span className="ds-notif-badge">{count > 99 ? "99+" : count}</span>}
      </button>
      {open && <div className="ds-popover__panel">
        <div className="ds-popover__identity">
          <strong>شكاوى جديدة</strong>
          {count > 0 && <span className="ds-notif-total">{count}</span>}
        </div>
        {!loaded ? (
          <p className="ds-popover__empty">جار التحميل</p>
        ) : rows.length === 0 ? (
          <p className="ds-popover__empty">لا توجد شكاوى جديدة.</p>
        ) : (
          <ul className="ds-note-list">
            {rows.map((row) => (
              <li key={row.id}>
                <a href={`/complaints/${row.id}/`}>
                  <span>{row.title}</span>
                  <small>
                    {row.return_reason
                      ? `أُعيدت للتوجيه إلى مفتش آخر · ${row.return_reason}`
                      : `${row.region_name} · ${formatDateTime(row.created_at)}`}
                  </small>
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>}
    </div>
  )
}

function UserMenu({ user, onSignOut, leaving }: { user: SessionUser; onSignOut: () => void; leaving: boolean }) {
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  const root = useAway(open, close)
  const name = user.display_name || user.username
  const initial = name.trim().slice(0, 1)
  return (
    <div className="ds-popover" ref={root}>
      <button type="button" className="ds-avatar" aria-label="حساب المستخدم" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <span aria-hidden="true">{initial}</span>
      </button>
      {open && (
        <div className="ds-popover__panel">
          <div className="ds-popover__identity">
            <span className="ds-avatar ds-avatar--md" aria-hidden="true">
              {initial}
            </span>
            <div className="ds-popover__who">
              <strong>{name}</strong>
              <span>
                <bdi>@{user.username}</bdi>
                {" · "}
                {ROLE_LABELS[user.role]}
              </span>
            </div>
          </div>
          <a className="ds-popover__item" href="/account/">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1A1.7 1.7 0 0 0 10 3.1V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
            </svg>
            <span>الإعدادات</span>
          </a>
          <div className="ds-popover__divider" aria-hidden="true" />
          <button className="ds-popover__item ds-popover__item--danger" type="button" disabled={leaving} onClick={onSignOut}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>تسجيل الخروج</span>
          </button>
        </div>
      )}
    </div>
  )
}

export function Shell({
  user,
  activeId,
  pageTitle,
  children,
}: {
  user: SessionUser
  activeId?: string
  pageTitle: ReactNode
  children: ReactNode
}) {
  const navigate = useNavigate()
  const { signOut, signIn } = useAuth()
  const [leaving, setLeaving] = useState(false)
  const [returning, setReturning] = useState(false)
  const [returnError, setReturnError] = useState("")
  const hello = greeting(user.display_name || user.username)
  const nav = navEntries(user).map((entry): NavEntry =>
    entry.items ? { id: entry.id, label: entry.label, items: entry.items } : { id: entry.id, label: entry.label, href: entry.href || "/" },
  )

  const onClick = (event: MouseEvent<HTMLDivElement>) => {
    const href = internalHref(event)
    if (!href) return
    event.preventDefault()
    navigate(href)
  }

  const onSignOut = async () => {
    setLeaving(true)
    await signOut()
    navigate(LOGIN_PATH, { replace: true })
  }

  const onReturn = async () => {
    setReturning(true)
    setReturnError("")
    const result = await apiRequest<SessionUser>("/api/auth/return/", { method: "POST" })
    setReturning(false)
    if (result.ok && result.data) {
      signIn(result.data)
      navigate("/users/")
      return
    }
    setReturnError(errorDetail(result.data) || "تعذّرت العودة إلى حسابك.")
  }

  const impersonator = user.impersonator
  const actingName = user.display_name || user.username

  return (
    <div className="app-frame" onClick={onClick}>
      <AppShell
        title="حماية المستهلك"
        subtitle="وزارة الاقتصاد الوطني"
        nav={nav}
        activeId={activeId}
        pageTitle={pageTitle}
        greeting={
          <div className="ds-hello">
            <span className="ds-hello__title">{hello.hello}</span>
            <span className="ds-hello__date">{hello.date}</span>
          </div>
        }
        tools={
          <div className="ds-shell__tools">
            <Notifications />
            <UserMenu user={user} leaving={leaving} onSignOut={onSignOut} />
          </div>
        }
      >
        {impersonator && (
          <div className="ds-impersonate" role="status">
            <p>
              تتصفح بحساب {actingName} (<bdi>@{user.username}</bdi>).
              {returnError && <span className="ds-impersonate__error">{returnError}</span>}
            </p>
            <Button size="sm" variant="secondary" loading={returning} onClick={onReturn}>
              العودة إلى حسابك
            </Button>
          </div>
        )}
        {children}
      </AppShell>
    </div>
  )
}
