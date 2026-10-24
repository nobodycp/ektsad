import { useEffect, type ReactNode } from "react"

export function Dialog({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: ReactNode
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [onClose])

  return (
    <div className="ds-dialog" onMouseDown={onClose}>
      <div
        className="ds-dialog__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ds-dialog-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="ds-dialog__head">
          <h2 id="ds-dialog-title">{title}</h2>
          <button type="button" className="ds-dialog__close" aria-label="إغلاق" onClick={onClose}>
            ×
          </button>
        </header>
        {children}
      </div>
    </div>
  )
}
