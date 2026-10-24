import { useCallback, useEffect, useState, type ReactNode } from "react"
import { ErrorState, LoadingState, STATUS_LABELS } from "../design-system"
import { errorDetail, type ActionResult, type ApiResult } from "../api"
import { FORBIDDEN_MESSAGE } from "../routes"

export const PAGE_SIZE = 20
export const ALL_ROWS = 100

export const STATUS_OPTIONS = STATUS_LABELS.map((status) => ({ value: status, label: status }))

export const OTHER_INSPECTOR_ACCEPTED = "استلم هذه الشكوى مفتش آخر."

export type Notice = { tone: "ok" | "error"; text: string } | null

export function NoticeLine({ notice }: { notice: Notice }) {
  if (!notice) return null
  return (
    <p className={notice.tone === "ok" ? "app-notice" : "app-alert"} role={notice.tone === "ok" ? "status" : "alert"}>
      {notice.text}
    </p>
  )
}

export function failureText(result: ApiResult<unknown>, fallback = "تعذّر تنفيذ الطلب. أعد المحاولة."): string {
  if (result.status === 0) return "تعذّر الاتصال بالخادم. تحقق من الشبكة وأعد المحاولة."
  if (result.status === 403) return errorDetail(result.data) === "Forbidden" ? FORBIDDEN_MESSAGE : errorDetail(result.data) ?? FORBIDDEN_MESSAGE
  return errorDetail(result.data) ?? fallback
}

/** Turns a bulk action reply into one line: failures win, because they need attention. */
export function actionNotice(result: ApiResult<ActionResult>, okText: string): Notice {
  if (!result.ok || !result.data) return { tone: "error", text: failureText(result) }
  const { succeeded, failed } = result.data
  if (failed.length > 0) {
    const reasons = Array.from(new Set(failed.map((f) => f.detail))).join(" ")
    const prefix = succeeded.length > 0 ? `${okText} (${succeeded.length}). تعذّر ${failed.length}: ` : ""
    return { tone: "error", text: `${prefix}${reasons}` }
  }
  return { tone: "ok", text: okText }
}

type LoadState<T> = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: T }

/**
 * Loads once per dependency change. `reload` refetches while the previous data stays on screen,
 * so a table does not flash empty after an action.
 */
export function useLoad<T>(load: () => Promise<ApiResult<T>>, deps: unknown[]) {
  const [state, setState] = useState<LoadState<T>>({ status: "loading" })
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    load().then((result) => {
      if (cancelled) return
      if (result.ok && result.data) setState({ status: "ready", data: result.data })
      else setState({ status: "error", message: failureText(result, "تعذّر تحميل البيانات.") })
    })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { state, reload }
}

export function Loaded<T>({
  state,
  onRetry,
  children,
}: {
  state: LoadState<T>
  onRetry: () => void
  children: (data: T) => ReactNode
}) {
  if (state.status === "loading") return <LoadingState />
  if (state.status === "error") return <ErrorState title="تعذّر التحميل" message={state.message} onRetry={onRetry} />
  return <>{children(state.data)}</>
}

const DATE_TIME = new Intl.DateTimeFormat("ar-u-nu-latn", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Asia/Hebron",
})

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : DATE_TIME.format(date)
}

export function todayInHebron(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Hebron" }).format(new Date())
}

export function fileName(path: string): string {
  return path.split("/").pop() || path
}

export function Section({
  title,
  note,
  aside,
  children,
}: {
  title: string
  note?: ReactNode
  aside?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="sheet" aria-label={title}>
      <header className="sheet__head">
        <div>
          <h2 className="sheet__heading">{title}</h2>
          {note && <p className="sheet__note">{note}</p>}
        </div>
        {aside}
      </header>
      {children}
    </section>
  )
}

export type Figure = { label: ReactNode; value: ReactNode; key: string }

export function Ledger({ figures, label }: { figures: Figure[]; label: string }) {
  return (
    <dl className="ledger" aria-label={label}>
      {figures.map((f) => (
        <div key={f.key} className="ledger__item">
          <dt className="ledger__label">{f.label}</dt>
          <dd className="ledger__value">{f.value}</dd>
        </div>
      ))}
    </dl>
  )
}
