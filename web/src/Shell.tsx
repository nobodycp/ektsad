import { useState, type MouseEvent, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { AppShell, Button } from "./design-system"
import type { SessionUser } from "./api"
import { useAuth } from "./auth"
import { navForRole } from "./routes"

const ROLE_LABELS: Record<SessionUser["role"], string> = {
  admin: "مدير النظام",
  governor: "محافظ",
  inspector: "مفتش",
  legal: "الشؤون القانونية",
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
  const { signOut } = useAuth()
  const [leaving, setLeaving] = useState(false)

  const onClick = (event: MouseEvent<HTMLDivElement>) => {
    const href = internalHref(event)
    if (!href) return
    event.preventDefault()
    navigate(href)
  }

  const onSignOut = async () => {
    setLeaving(true)
    await signOut()
    navigate("/", { replace: true })
  }

  return (
    <div className="app-frame" onClick={onClick}>
      <AppShell
        title="منظومة حماية المستهلك"
        subtitle={`${user.display_name || user.username} · ${ROLE_LABELS[user.role]}`}
        nav={navForRole(user.role).map((route) => ({ id: route.id, label: route.label, href: route.path }))}
        activeId={activeId}
        pageTitle={pageTitle}
        headerActions={
          <Button variant="ghost" size="sm" loading={leaving} onClick={onSignOut}>
            تسجيل الخروج
          </Button>
        }
      >
        {children}
      </AppShell>
    </div>
  )
}
