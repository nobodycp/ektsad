import type { Role, RouteFlag, SessionUser } from "./api"

export type AppRoute = {
  id: string
  path: string
  label: string
  roles: Role[]
  /** Non-admin roles also need this session flag. Admin always passes. */
  flag?: RouteFlag
  /** Detail routes highlight their parent item and stay out of the sidebar. */
  navId?: string
  /** Sidebar group. Ungrouped routes stay as top-level links. */
  group?: "reports" | "publish" | "admin"
}

const ALL: Role[] = ["admin", "governor", "inspector", "legal"]

const GROUP_LABELS = { reports: "التقارير", publish: "النشر", admin: "الإدارة" } as const

export const APP_ROUTES: AppRoute[] = [
  { id: "overview", path: "/overview/", label: "نظرة عامة", roles: ALL },
  { id: "complaints", path: "/complaints/", label: "الشكاوى", roles: ALL },
  { id: "complaint", path: "/complaints/:id/", label: "الشكوى", roles: ALL, navId: "complaints" },
  { id: "staff-report", path: "/reports/staff/", label: "أداء الموظفين", roles: ["admin"], group: "reports" },
  { id: "complaints-report", path: "/reports/complaints/", label: "تقرير الشكاوى", roles: ["admin"], group: "reports" },
  { id: "governor-staff", path: "/governor/staff/", label: "أداء الموظفين", roles: ["governor"], group: "reports" },
  { id: "governor-report", path: "/governor/report/", label: "تقرير الشكاوى", roles: ["governor"], group: "reports" },
  { id: "prices", path: "/prices/", label: "الأسعار", roles: ALL, flag: "can_publish_prices", group: "publish" },
  { id: "crossings", path: "/crossings/", label: "المعابر", roles: ALL, flag: "can_publish_crossings", group: "publish" },
  { id: "field-missions", path: "/field-missions/", label: "مهمات ميدانية", roles: ALL, flag: "can_view_field_missions", group: "admin" },
  { id: "users", path: "/users/", label: "المستخدمون", roles: ["admin"], group: "admin" },
  { id: "governorates", path: "/governorates/", label: "المحافظات", roles: ["admin"], group: "admin" },
  { id: "regions", path: "/regions/", label: "المناطق", roles: ["admin"], group: "admin" },
  { id: "system-settings", path: "/system-settings/", label: "إعدادات النظام", roles: ["admin"], group: "admin" },
  { id: "telegram-settings", path: "/telegram-settings/", label: "إعدادات تلغرام", roles: ["admin"], group: "admin" },
  { id: "telegram-health", path: "/telegram-health/", label: "حالة تلغرام", roles: ["admin"], group: "admin" },
  { id: "account", path: "/account/", label: "الإعدادات", roles: ALL, navId: "account" },
]

export const PUBLIC_PATH = "/"
export const LOGIN_PATH = "/login/"
export const HOME_PATH = "/overview/"

export function navEntries(user: SessionUser): Array<{ id: string; label: string; href?: string; items?: { id: string; label: string; href: string }[] }> {
  const visible = APP_ROUTES.filter((route) => !route.navId && canOpen(route, user))
  const entries: Array<{ id: string; label: string; href?: string; items?: { id: string; label: string; href: string }[] }> = []
  const seen = new Set<string>()
  for (const route of visible) {
    if (!route.group) {
      entries.push({ id: route.id, label: route.label, href: route.path })
      continue
    }
    if (seen.has(route.group)) continue
    seen.add(route.group)
    entries.push({
      id: route.group,
      label: GROUP_LABELS[route.group],
      items: visible.filter((item) => item.group === route.group).map((item) => ({ id: item.id, label: item.label, href: item.path })),
    })
  }
  return entries
}

export const FORBIDDEN_MESSAGE = "لا تملك صلاحية الوصول إلى هذه الصفحة."

export function canOpen(route: AppRoute, user: SessionUser): boolean {
  if (!route.roles.includes(user.role)) return false
  if (!route.flag || user.role === "admin") return true
  return Boolean(user[route.flag])
}

export function navForUser(user: SessionUser): AppRoute[] {
  return APP_ROUTES.filter((route) => !route.navId && canOpen(route, user))
}
