import { Button } from "./Button"

export type RowAction = {
  id: string
  label: string
  onSelect: () => void
  tone?: "default" | "danger"
  disabled?: boolean
}

export function RowActions({ actions }: { actions: RowAction[] }) {
  if (actions.length === 0) return null
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
