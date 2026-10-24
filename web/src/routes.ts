import type { PublishFlag, Role, SessionUser } from "./api"

export type AppRoute = {
  id: string
  path: string
  label: string
  roles: Role[]
  /** Non-admin roles also need this session flag. Admin always passes. */
  flag?: PublishFlag
  /** Detail routes highlight their parent item and stay out of the sidebar. */
  navId?: string
}

const ALL: Role[] = ["admin", "governor", "inspector", "legal"]

export const APP_ROUTES: AppRoute[] = [
  { id: "governorates", path: "/governorates/", label: "المحافظات", roles: ["admin"] },
  { id: "regions", path: "/regions/", label: "المناطق", roles: ["admin"] },
  { id: "users", path: "/users/", label: "المستخدمون", roles: ["admin"] },
  { id: "complaints", path: "/complaints/", label: "الشكاوى", roles: ALL },
  { id: "complaint", path: "/complaints/:id/", label: "الشكوى", roles: ALL, navId: "complaints" },
  { id: "governor-report", path: "/governor/report/", label: "التقرير اليومي", roles: ["governor"] },
  { id: "reports", path: "/reports/", label: "التقارير", roles: ["admin"] },
  { id: "telegram-health", path: "/telegram-health/", label: "صحة تلغرام", roles: ["admin"] },
  { id: "prices", path: "/prices/", label: "الأسعار", roles: ALL, flag: "can_publish_prices" },
  { id: "crossings", path: "/crossings/", label: "المعابر", roles: ALL, flag: "can_publish_crossings" },
  { id: "account", path: "/account/", label: "الإعدادات", roles: ALL },
]

export const PUBLIC_PATH = "/"
export const LOGIN_PATH = "/login/"
export const HOME_PATH = "/complaints/"

export const FORBIDDEN_MESSAGE = "لا تملك صلاحية الوصول إلى هذه الصفحة."

export function canOpen(route: AppRoute, user: SessionUser): boolean {
  if (!route.roles.includes(user.role)) return false
  if (!route.flag || user.role === "admin") return true
  return Boolean(user[route.flag])
}

export function navForUser(user: SessionUser): AppRoute[] {
  return APP_ROUTES.filter((route) => !route.navId && canOpen(route, user))
}
