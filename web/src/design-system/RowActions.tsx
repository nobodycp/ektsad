import { useEffect, useRef, useState } from "react"
import { Button } from "./Button"

export type RowAction = {
  id: string
  label: string
  onSelect: () => void
  tone?: "default" | "danger"
  disabled?: boolean
}

function ActionMenu({ actions }: { actions: RowAction[] }) {
  const [open, setOpen] = useState(false)
  const [box, setBox] = useState<{ top: number; left: number } | null>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || !buttonRef.current) return
    const rect = buttonRef.current.getBoundingClientRect()
    setBox({ top: rect.bottom + 4, left: rect.left })
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (buttonRef.current?.contains(target) || panelRef.current?.contains(target)) return
      setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false)
    }
    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className="ds-icon-btn"
        aria-label="إجراءات"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <svg className="ds-rowmenu__dots" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="5" r="1.4" />
          <circle cx="12" cy="12" r="1.4" />
          <circle cx="12" cy="19" r="1.4" />
        </svg>
      </button>
      {open && box && (
        <div ref={panelRef} className="ds-rowmenu" role="menu" style={{ top: box.top, left: box.left }}>
          {actions.map((action) => (
            <button
              key={action.id}
              type="button"
              role="menuitem"
              className={action.tone === "danger" ? "ds-rowmenu__item is-danger" : "ds-rowmenu__item"}
              disabled={action.disabled}
              onClick={() => {
                setOpen(false)
                action.onSelect()
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </>
  )
}

export function RowActions({ actions, menu = false }: { actions: RowAction[]; menu?: boolean }) {
  if (actions.length === 0) return null
  if (menu) return <ActionMenu actions={actions} />
  return (
    <div className="ds-rowactions">
      {actions.map((a) => (
        <Button
          key={a.id}
          size="sm"
          variant={a.tone === "danger" ? "danger" : "ghost"}
          disabled={a.disabled}
          onClick={a.onSelect}
        >
          {a.label}
        </Button>
      ))}
    </div>
  )
}
