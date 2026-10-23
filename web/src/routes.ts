import type { Role } from "./api"

export type AppRoute = { id: string; path: string; label: string; roles: Role[] }

const ALL: Role[] = ["admin", "governor", "inspector", "legal"]

export const APP_ROUTES: AppRoute[] = [
  { id: "governorates", path: "/governorates/", label: "المحافظات", roles: ["admin"] },
  { id: "regions", path: "/regions/", label: "المناطق", roles: ["admin"] },
  { id: "users", path: "/users/", label: "المستخدمون", roles: ["admin"] },
  { id: "complaints", path: "/complaints/", label: "الشكاوى", roles: ALL },
  { id: "governor-report", path: "/governor/report/", label: "التقرير اليومي", roles: ["governor"] },
  { id: "reports", path: "/reports/", label: "التقارير", roles: ["admin"] },
  { id: "telegram-health", path: "/telegram-health/", label: "صحة تلغرام", roles: ["admin"] },
  { id: "prices", path: "/prices/", label: "الأسعار", roles: ["admin"] },
  { id: "crossings", path: "/crossings/", label: "المعابر", roles: ["admin"] },
  { id: "account", path: "/account/", label: "الإعدادات", roles: ALL },
]

export const HOME_PATH = "/complaints/"

export const FORBIDDEN_MESSAGE = "لا تملك صلاحية الوصول إلى هذه الصفحة."

export function navForRole(role: Role): AppRoute[] {
  return APP_ROUTES.filter((route) => route.roles.includes(role))
}
