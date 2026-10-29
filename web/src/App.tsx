import type { ReactNode } from "react"
import { Navigate, Route, Routes, useLocation } from "react-router-dom"
import { EmptyState, LoadingState } from "./design-system"
import type { SessionUser } from "./api"
import { AuthProvider, useAuth } from "./auth"
import { APP_ROUTES, FORBIDDEN_MESSAGE, LOGIN_PATH, PUBLIC_PATH, canOpen, type AppRoute } from "./routes"
import { Shell } from "./Shell"
import { LoginPage } from "./pages/LoginPage"
import { AccountPage } from "./pages/AccountPage"
import { PublicPage } from "./pages/PublicPage"
import { ComplaintsPage } from "./pages/ComplaintsPage"
import { ComplaintPage } from "./pages/ComplaintPage"
import { RolesPage } from "./pages/RolesPage"
import { UsersPage } from "./pages/UsersPage"
import { GeographyPage } from "./pages/GeographyPage"
import { OverviewPage } from "./pages/OverviewPage"
import { AdminReportsPage, GovernorReportPage } from "./pages/ReportsPage"
import { PublicationsPage } from "./pages/PublicationsPage"
import { BotButtonsPage } from "./pages/BotButtonsPage"
import { SystemSettingsPage, TelegramSettingsPage } from "./pages/SettingsPages"
import { TelegramHealthPage } from "./pages/TelegramHealthPage"
import { FieldMissionPage } from "./pages/FieldMissionPage"
import { FieldMissionsPage } from "./pages/FieldMissionsPage"
import "./app.css"

function FullPageLoading() {
  return (
    <div className="app-center" dir="rtl" lang="ar">
      <LoadingState />
    </div>
  )
}

function pageFor(route: AppRoute, user: SessionUser): ReactNode {
  switch (route.id) {
    case "account":
      return <AccountPage />
    case "overview":
      return <OverviewPage user={user} />
    case "complaints":
      return <ComplaintsPage user={user} />
    case "field-missions":
      return <FieldMissionsPage user={user} />
    case "field-mission":
      return <FieldMissionPage user={user} />
    case "complaint":
      return <ComplaintPage user={user} />
    case "users":
      return <UsersPage />
    case "roles":
      return <RolesPage />
    case "governorates":
      return <GeographyPage kind="governorates" />
    case "regions":
      return <GeographyPage kind="regions" />
    case "governor-report":
      return <GovernorReportPage part="complaints" />
    case "governor-staff":
      return <GovernorReportPage part="staff" />
    case "complaints-report":
      return <AdminReportsPage part="complaints" />
    case "staff-report":
      return <AdminReportsPage part="staff" />
    case "system-settings":
      return <SystemSettingsPage />
    case "telegram-settings":
      return <TelegramSettingsPage />
    case "telegram-buttons":
      return <BotButtonsPage />
    case "prices":
      return <PublicationsPage kind="prices" user={user} />
    case "crossings":
      return <PublicationsPage kind="crossings" user={user} />
    case "telegram-health":
      return <TelegramHealthPage />
    default:
      return null
  }
}

function Protected({ children }: { children: (user: SessionUser) => ReactNode }) {
  const { session } = useAuth()
  const location = useLocation()
  if (session.status === "loading") return <FullPageLoading />
  if (session.status === "anonymous") return <Navigate to={LOGIN_PATH} replace state={{ from: location.pathname }} />
  return <>{children(session.user)}</>
}

function RoutePage({ route }: { route: AppRoute }) {
  return (
    <Protected>
      {(user) =>
        canOpen(route, user) ? (
          <Shell user={user} activeId={route.navId ?? route.id} pageTitle={route.label}>
            {pageFor(route, user)}
          </Shell>
        ) : (
          <Shell user={user} pageTitle={route.label}>
            <EmptyState title={FORBIDDEN_MESSAGE} />
          </Shell>
        )
      }
    </Protected>
  )
}

function NotFound() {
  return (
    <Protected>
      {(user) => (
        <Shell user={user} pageTitle="الصفحة غير موجودة">
          <EmptyState title="لم نجد الصفحة المطلوبة." description="تحقق من الرابط أو اختر صفحة من القائمة." />
        </Shell>
      )}
    </Protected>
  )
}

function AppRoutes() {
  return (
    <Routes>
      <Route path={PUBLIC_PATH} element={<PublicPage />} />
      <Route path={LOGIN_PATH} element={<LoginPage />} />
      {APP_ROUTES.map((route) => (
        <Route key={route.id} path={route.path} element={<RoutePage route={route} />} />
      ))}
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
