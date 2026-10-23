import type { ReactNode } from "react"
import { Button } from "./Button"

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="ds-state" data-kind="empty">
      <span className="ds-state__mark" aria-hidden="true" />
      <p className="ds-state__title">{title}</p>
      {description && <p className="ds-state__desc">{description}</p>}
      {action}
    </div>
  )
}

export function LoadingState({ label = "جار التحميل" }: { label?: string }) {
  return (
    <div className="ds-state" data-kind="loading" role="status" aria-live="polite">
      <span className="ds-loading__bar" aria-hidden="true" />
      <p className="ds-state__desc">{label}</p>
    </div>
  )
}

export function ErrorState({
  title = "حدث خطأ",
  message,
  onRetry,
}: {
  title?: string
  message?: string
  onRetry?: () => void
}) {
  return (
    <div className="ds-state" data-kind="error" role="alert">
      <span className="ds-state__mark" aria-hidden="true" />
      <p className="ds-state__title">{title}</p>
      {message && <p className="ds-state__desc">{message}</p>}
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          إعادة المحاولة
        </Button>
      )}
    </div>
  )
}
