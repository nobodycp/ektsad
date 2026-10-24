import { useState, type FormEvent } from "react"
import { Button, DataTable, Dialog, Select, TextField, type Column, type RowAction } from "../design-system"
import { apiRequest, withQuery, type Page, type RegionPlace } from "../api"
import { Loaded, NoticeLine, PAGE_SIZE, failureText, useLoad, type Notice } from "./common"
import { nameOf, optionsOf, useAdminGeography } from "./geo"

type Kind = "governorates" | "regions"

const COPY: Record<Kind, { create: string; empty: string; noun: string }> = {
  governorates: { create: "محافظة جديدة", empty: "لا توجد محافظات بعد.", noun: "المحافظة" },
  regions: { create: "منطقة جديدة", empty: "لا توجد مناطق بعد.", noun: "المنطقة" },
}

type Row = { id: number; name: string; governorate?: number }
const rowId = (row: Row) => row.id

export function GeographyPage({ kind }: { kind: Kind }) {
  const copy = COPY[kind]
  const [page, setPage] = useState(1)
  const [name, setName] = useState("")
  const [governorate, setGovernorate] = useState("")
  const [errors, setErrors] = useState<{ name?: string; governorate?: string }>({})
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Row | null>(null)
  const [editName, setEditName] = useState("")
  const [removing, setRemoving] = useState<Row | null>(null)
  const geo = useAdminGeography(version)

  const { state, reload } = useLoad(
    () => apiRequest<Page<Row>>(withQuery(`/api/${kind}/`, { page, page_size: PAGE_SIZE })),
    [kind, page],
  )

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice(null)
    const found: typeof errors = {}
    if (!name.trim()) found.name = `أدخل اسم ${copy.noun}.`
    if (kind === "regions" && !governorate) found.governorate = "اختر المحافظة."
    setErrors(found)
    if (Object.keys(found).length) return
    const body = kind === "regions" ? { name: name.trim(), governorate: Number(governorate) } : { name: name.trim() }
    setBusy(true)
    const result = await apiRequest<RegionPlace>(`/api/${kind}/`, { method: "POST", body })
    setBusy(false)
    if (result.ok) {
      setNotice({ tone: "ok", text: `تمت إضافة ${copy.noun} ${name.trim()}.` })
      setName("")
      setCreating(false)
      setVersion((v) => v + 1)
      reload()
    } else {
      setNotice({ tone: "error", text: failureText(result, `تعذّر حفظ ${copy.noun}. قد يكون الاسم مستخدماً.`) })
    }
  }

  const rename = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!editing || !editName.trim()) return
    setBusy(true)
    const result = await apiRequest(`/api/${kind}/${editing.id}/`, { method: "PATCH", body: { name: editName.trim() } })
    setBusy(false)
    if (result.ok) {
      setNotice({ tone: "ok", text: `تم تعديل اسم ${copy.noun}.` })
      setEditing(null)
      setVersion((v) => v + 1)
      reload()
    } else {
      setNotice({ tone: "error", text: failureText(result) })
    }
  }

  const remove = async (row: Row) => {
    setNotice(null)
    const result = await apiRequest(`/api/${kind}/${row.id}/`, { method: "DELETE" })
    setNotice(result.ok ? { tone: "ok", text: `تم حذف ${copy.noun} ${row.name}.` } : { tone: "error", text: failureText(result) })
    if (result.ok) {
      setVersion((v) => v + 1)
      reload()
    }
  }

  const columns: Column<Row>[] = [{ key: "name", header: "الاسم", render: (row) => row.name }]
  if (kind === "regions")
    columns.push({ key: "governorate", header: "المحافظة", render: (row) => nameOf(geo.governorates, row.governorate) })

  return (
    <div className="page">
      <div className="page__bar">
        <Button onClick={() => setCreating(true)}>{copy.create}</Button>
      </div>
      <NoticeLine notice={notice} />
      {creating && (
        <Dialog title={copy.create} onClose={() => setCreating(false)}>
          <form className="sheet__form" onSubmit={onSubmit} noValidate>
            {kind === "regions" && (
              <Select
                label="المحافظة"
                name="governorate"
                placeholder="اختر المحافظة"
                options={optionsOf(geo.governorates)}
                value={governorate}
                onChange={(e) => setGovernorate(e.target.value)}
                error={errors.governorate}
                required
              />
            )}
            <TextField label="الاسم" name="name" value={name} onChange={(e) => setName(e.target.value)} error={errors.name} required />
            <div className="sheet__actions">
              <Button type="submit" loading={busy}>
                إضافة
              </Button>
              <Button variant="ghost" onClick={() => setCreating(false)}>
                إلغاء
              </Button>
            </div>
          </form>
        </Dialog>
      )}
      {editing && (
        <Dialog title={`تعديل ${copy.noun}`} onClose={() => setEditing(null)}>
          <form className="sheet__form" onSubmit={rename} noValidate>
            <TextField label="الاسم" name="edit_name" value={editName} onChange={(e) => setEditName(e.target.value)} required />
            <div className="sheet__actions">
              <Button type="submit" loading={busy}>
                حفظ الاسم
              </Button>
              <Button variant="ghost" onClick={() => setEditing(null)}>
                إلغاء
              </Button>
            </div>
          </form>
        </Dialog>
      )}
      {removing && (
        <Dialog title={`حذف ${copy.noun}`} onClose={() => setRemoving(null)}>
          <p>سيُحذف {removing.name}. السجل المرتبط بشكاوى لا يُحذف.</p>
          <div className="sheet__actions">
            <Button
              variant="danger"
              loading={busy}
              onClick={async () => {
                await remove(removing)
                setRemoving(null)
              }}
            >
              تأكيد الحذف
            </Button>
            <Button variant="ghost" onClick={() => setRemoving(null)}>
              إلغاء
            </Button>
          </div>
        </Dialog>
      )}
      <Loaded state={state} onRetry={reload}>
        {(data) => (
          <DataTable
            caption={kind === "regions" ? "المناطق" : "المحافظات"}
            columns={columns}
            rows={data.results}
            getRowId={rowId}
            emptyTitle={copy.empty}
            rowActions={(row): RowAction[] => [
              { id: "rename", label: "تعديل الاسم", onSelect: () => { setEditing(row); setEditName(row.name) } },
              { id: "delete", label: "حذف", tone: "danger", onSelect: () => setRemoving(row) },
            ]}
            pagination={{ page: data.page, pageSize: data.page_size, total: data.count, onPageChange: setPage }}
          />
        )}
      </Loaded>
    </div>
  )
}
