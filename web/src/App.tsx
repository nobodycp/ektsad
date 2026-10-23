import type { ReactNode } from "react"
import { Navigate, Route, Routes, useLocation } from "react-router-dom"
import { EmptyState, LoadingState } from "./design-system"
import type { SessionUser } from "./api"
import { AuthProvider, useAuth } from "./auth"
import { APP_ROUTES, FORBIDDEN_MESSAGE, type AppRoute } from "./routes"
import { Shell } from "./Shell"
import { LoginPage } from "./pages/LoginPage"
import { AccountPage } from "./pages/AccountPage"
import { PlaceholderPage } from "./pages/PlaceholderPage"
import "./app.css"

function FullPageLoading() {
  return (
    <div className="app-center" dir="rtl" lang="ar">
      <LoadingState />
    </div>
  )
}

function pageFor(route: AppRoute): ReactNode {
  if (route.id === "account") return <AccountPage />
  return <PlaceholderPage label={route.label} />
}

function Protected({ children }: { children: (user: SessionUser) => ReactNode }) {
  const { session } = useAuth()
  const location = useLocation()
  if (session.status === "loading") return <FullPageLoading />
  if (session.status === "anonymous") return <Navigate to="/" replace state={{ from: location.pathname }} />
  return <>{children(session.user)}</>
}

function RoutePage({ route }: { route: AppRoute }) {
  return (
    <Protected>
      {(user) =>
        route.roles.includes(user.role) ? (
          <Shell user={user} activeId={route.id} pageTitle={route.label}>
            {pageFor(route)}
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
      <Route path="/" element={<LoginPage />} />
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
