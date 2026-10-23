import { Button } from "./Button"

export type RowId = string | number

export type BulkAction = {
  id: string
  label: string
  onRun: (ids: RowId[]) => void
  tone?: "default" | "danger"
}

export type BulkActionBarProps = {
  actions: BulkAction[]
  selectedIds: RowId[]
  onClear: () => void
}

export function BulkActionBar({ actions, selectedIds, onClear }: BulkActionBarProps) {
  if (actions.length === 0 || selectedIds.length === 0) return null
  return (
    <div className="ds-bulkbar" data-testid="bulk-action-bar" role="region" aria-label="إجراءات جماعية">
      <span className="ds-bulkbar__count" aria-live="polite">
        تم تحديد {selectedIds.length}
      </span>
      {actions.map((a) => (
        <Button
          key={a.id}
          size="sm"
          variant={a.tone === "danger" ? "danger" : "secondary"}
          onClick={() => a.onRun(selectedIds)}
        >
          {a.label}
        </Button>
      ))}
      <Button size="sm" variant="ghost" onClick={onClear}>
        إلغاء التحديد
      </Button>
    </div>
  )
}
