import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { BulkActionBar, type BulkAction, type RowId } from "./BulkActionBar"
import { Button } from "./Button"
import { RowActions, type RowAction } from "./RowActions"
import { EmptyState } from "./states"

export type Column<T> = {
  key: string
  header: string
  render: (row: T) => ReactNode
  width?: number | string
}

export type Pagination = {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export type DataTableProps<T> = {
  columns: Column<T>[]
  rows: T[]
  getRowId: (row: T) => RowId
  rowActions?: (row: T) => RowAction[]
  bulkActions?: BulkAction[]
  pagination?: Pagination
  caption?: string
  emptyTitle?: string
  getRowLabel?: (row: T) => string
}

function SelectAll({ checked, indeterminate, onChange }: { checked: boolean; indeterminate: boolean; onChange: () => void }) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate
  }, [indeterminate])
  return <input ref={ref} type="checkbox" aria-label="تحديد الكل" checked={checked} onChange={onChange} />
}

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  rowActions,
  bulkActions = [],
  pagination,
  caption,
  emptyTitle = "لا توجد بيانات",
  getRowLabel,
}: DataTableProps<T>) {
  const selectable = bulkActions.length > 0
  const [selected, setSelected] = useState<RowId[]>([])

  const rowIds = useMemo(() => rows.map(getRowId), [rows, getRowId])
  const visibleSelected = selected.filter((id) => rowIds.includes(id))
  const allSelected = rowIds.length > 0 && visibleSelected.length === rowIds.length

  const labelFor = (row: T) => {
    if (getRowLabel) return getRowLabel(row)
    const first = columns[0]?.render(row)
    return typeof first === "string" || typeof first === "number" ? String(first) : String(getRowId(row))
  }

  const toggle = (id: RowId) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  const toggleAll = () => setSelected(allSelected ? [] : rowIds)

  const pageCount = pagination ? Math.max(1, Math.ceil(pagination.total / pagination.pageSize)) : 1

  return (
    <section className="ds-table-panel">
      {selectable && (
        <BulkActionBar actions={bulkActions} selectedIds={visibleSelected} onClear={() => setSelected([])} />
      )}
      {rows.length === 0 ? (
        <EmptyState title={emptyTitle} />
      ) : (
        <div className="ds-table-scroll">
          <table className="ds-table">
            {caption && <caption className="ds-visually-hidden">{caption}</caption>}
            <thead>
              <tr>
                {selectable && (
                  <th className="ds-table__select" scope="col">
                    <SelectAll
                      checked={allSelected}
                      indeterminate={visibleSelected.length > 0 && !allSelected}
                      onChange={toggleAll}
                    />
                  </th>
                )}
                {columns.map((c) => (
                  <th key={c.key} scope="col" style={c.width ? { width: c.width } : undefined}>
                    {c.header}
                  </th>
                ))}
                {rowActions && (
                  <th className="ds-table__actions" scope="col">
                    <span className="ds-visually-hidden">إجراءات</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const id = getRowId(row)
                const isSelected = visibleSelected.includes(id)
                return (
                  <tr key={id} aria-selected={selectable ? isSelected : undefined}>
                    {selectable && (
                      <td className="ds-table__select">
                        <input
                          type="checkbox"
                          aria-label={`تحديد ${labelFor(row)}`}
                          checked={isSelected}
                          onChange={() => toggle(id)}
                        />
                      </td>
                    )}
                    {columns.map((c) => (
                      <td key={c.key}>{c.render(row)}</td>
                    ))}
                    {rowActions && (
                      <td className="ds-table__actions">
                        <RowActions actions={rowActions(row)} />
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {pagination && (
        <nav className="ds-pagination" aria-label="ترقيم الصفحات">
          <span>
            صفحة {pagination.page} من {pageCount}
          </span>
          <span>إجمالي {pagination.total}</span>
          <div className="ds-pagination__controls">
            <Button
              size="sm"
              variant="secondary"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
            >
              السابق
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={pagination.page >= pageCount}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
            >
              التالي
            </Button>
          </div>
        </nav>
      )}
    </section>
  )
}
