import type { ReactNode } from "react"

export type TimelineEvent = {
  id: string
  title: string
  at: string
  actor?: string
  body?: ReactNode
}

export function Timeline({ events, label = "سجل الإجراءات" }: { events: TimelineEvent[]; label?: string }) {
  return (
    <ol className="ds-timeline" aria-label={label}>
      {events.map((e) => (
        <li key={e.id} className="ds-timeline__item">
          <span className="ds-timeline__dot" aria-hidden="true" />
          <p className="ds-timeline__title">{e.title}</p>
          <span className="ds-timeline__meta">
            <time dateTime={e.at}>{e.at}</time>
            {e.actor && <> · {e.actor}</>}
          </span>
          {e.body && <div className="ds-timeline__body">{e.body}</div>}
        </li>
      ))}
    </ol>
  )
}
