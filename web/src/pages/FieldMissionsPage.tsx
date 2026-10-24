import { useEffect, useState, type FormEvent } from "react"
import {
  Button,
  DataTable,
  Dialog,
  FileField,
  FilterBar,
  Select,
  TextArea,
  TextField,
  type Column,
  type FilterField,
  type FilterValues,
} from "../design-system"
import { apiRequest, apiUpload, withQuery, type FieldMission, type Page, type SessionUser, type UserRow } from "../api"
import { Loaded, NoticeLine, PAGE_SIZE, failureText, formatDateTime, useLoad, type Notice } from "./common"
import { optionsOf, useAdminGeography } from "./geo"

export const MISSION_KINDS = ["ضبط", "تحفظ", "إثبات حالة", "مصادرة", "إتلاف", "عينات فحص", "أخرى"] as const

const KIND_OPTIONS = MISSION_KINDS.map((kind) => ({ value: kind, label: kind }))

const SCHEMA: FilterField[] = [
  { type: "search", key: "q", label: "بحث", placeholder: "اسم المحل" },
  { type: "select", key: "kind", label: "نوع المهمة", options: KIND_OPTIONS },
]

const rowId = (row: FieldMission) => row.id

export function canOpenMission(user: SessionUser) {
  if (user.role === "admin") return true
  if (user.role !== "governor" && user.role !== "inspector") return false
  return user.can_open_field_missions
}

function MissionForm({ user, onSaved, onCancel }: { user: SessionUser; onSaved: (notice: Notice) => void; onCancel: () => void }) {
  const geo = useAdminGeography()
  const [kind, setKind] = useState("")
  const [details, setDetails] = useState("")
  const [placeName, setPlaceName] = useState("")
  const [phone, setPhone] = useState("")
  const [image, setImage] = useState<File | null>(null)
  const [governorate, setGovernorate] = useState("")
  const [scope, setScope] = useState<"one" | "all">("one")
  const [inspector, setInspector] = useState("")
  const [inspectors, setInspectors] = useState<UserRow[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)
  const assigns = user.role === "admin" || user.role === "governor"
  const governorateId = user.role === "governor" ? user.governorate : Number(governorate) || null

  useEffect(() => {
    if (!assigns || !governorateId) {
      setInspectors([])
      return
    }
    let cancelled = false
    const query = user.role === "admin" ? { governorate: governorateId } : {}
    apiRequest<Page<UserRow>>(withQuery("/api/users/", { role: "inspector", is_active: "1", page_size: 100, ...query })).then((result) => {
      if (!cancelled) setInspectors(result.data?.results ?? [])
    })
    return () => {
      cancelled = true
    }
  }, [assigns, governorateId, user.role])

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const found: Record<string, string> = {}
    if (!kind) found.kind = "اختر نوع المهمة."
    if (!details.trim()) found.details = "التفاصيل مطلوبة."
    if (!placeName.trim()) found.place_name = "اسم المحل مطلوب."
    if (!phone.trim()) found.phone = "رقم الجوال مطلوب."
    if (user.role === "admin" && !governorate) found.governorate = "اختر المحافظة."
    if (assigns && scope === "one" && !inspector) found.inspector = "اختر المفتش."
    setErrors(found)
    if (Object.keys(found).length) return
    const form = new FormData()
    form.set("kind", kind)
    form.set("details", details.trim())
    form.set("place_name", placeName.trim())
    form.set("phone", phone.trim())
    if (image) form.set("image", image)
    if (user.role === "admin") form.set("governorate", governorate)
    if (assigns) {
      form.set("scope", scope)
      if (scope === "one") form.set("inspector", inspector)
    }
    setBusy(true)
    const result = await apiUpload("/api/field-missions/", form)
    setBusy(false)
    if (result.ok) onSaved({ tone: "ok", text: "تم تسجيل المهمة الميدانية." })
    else setNotice({ tone: "error", text: failureText(result) })
  }

  return (
    <form className="sheet__form" onSubmit={onSubmit} noValidate>
      <div className="sheet__grid">
        <Select label="نوع المهمة" name="kind" placeholder="اختر النوع" options={KIND_OPTIONS} value={kind} onChange={(e) => setKind(e.target.value)} error={errors.kind} required />
        <TextArea label="تفاصيل المهمة" name="details" rows={4} value={details} onChange={(e) => setDetails(e.target.value)} error={errors.details} required />
        <TextField label="اسم المحل" name="place_name" value={placeName} onChange={(e) => setPlaceName(e.target.value)} error={errors.place_name} required />
        <TextField label="رقم الجوال" name="phone" value={phone} onChange={(e) => setPhone(e.target.value)} error={errors.phone} required dir="ltr" />
        <FileField label="صورة" name="image" accept="image/jpeg,image/png,image/webp" hint="اختيارية. jpeg أو png أو webp بحد 5 ميغابايت." onChange={(e) => setImage(e.target.files?.[0] ?? null)} />
        {user.role === "admin" && (
          <Select
            label="المحافظة"
            name="governorate"
            placeholder="اختر المحافظة"
            options={optionsOf(geo.governorates)}
            value={governorate}
            onChange={(e) => {
              setGovernorate(e.target.value)
              setInspector("")
            }}
            error={errors.governorate}
            required
          />
        )}
        {assigns && (
          <Select
            label="التوجيه"
            name="scope"
            options={[
              { value: "one", label: "مفتش واحد" },
              { value: "all", label: "كل المفتشين" },
            ]}
            value={scope}
            onChange={(e) => setScope(e.target.value as "one" | "all")}
          />
        )}
        {assigns && scope === "one" && (
          <Select
            label="المفتش"
            name="inspector"
            placeholder={governorateId ? "اختر المفتش" : "اختر المحافظة أولاً"}
            options={inspectors.map((row) => ({ value: String(row.id), label: row.display_name || row.username }))}
            value={inspector}
            disabled={!governorateId}
            onChange={(e) => setInspector(e.target.value)}
            error={errors.inspector}
            required
          />
        )}
      </div>
      {user.role === "inspector" && <p className="sheet__note">ستكون أنت المسؤول عن هذه المهمة.</p>}
      <NoticeLine notice={notice} />
      <div className="sheet__actions">
        <Button type="submit" loading={busy}>
          تسجيل المهمة
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  )
}

function MissionView({ mission }: { mission: FieldMission }) {
  const people = mission.assignees.map((row) => row.name).filter(Boolean).join("، ") || "—"
  return (
    <div className="sheet__form">
      <div className="sheet__grid">
        <p><span className="ds-field__label">النوع</span><br />{mission.kind}</p>
        <p><span className="ds-field__label">المحل</span><br />{mission.place_name}</p>
        <p><span className="ds-field__label">الجوال</span><br /><bdi>{mission.phone}</bdi></p>
        <p><span className="ds-field__label">المحافظة</span><br />{mission.governorate_name}{mission.region_name ? `، ${mission.region_name}` : ""}</p>
        <p><span className="ds-field__label">المسؤولون</span><br />{people}</p>
        <p><span className="ds-field__label">أنشأها</span><br />{mission.created_by_name || "—"} · {formatDateTime(mission.created_at)}</p>
      </div>
      <p className="sheet__note">{mission.details}</p>
      {mission.has_image && <img className="ds-mission-photo" src={`/api/media/field-missions/${mission.id}/`} alt={mission.place_name} />}
    </div>
  )
}

export function FieldMissionsPage({ user }: { user: SessionUser }) {
  const [filters, setFilters] = useState<FilterValues>({})
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState<FieldMission | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const { state, reload } = useLoad(
    () => apiRequest<Page<FieldMission>>(withQuery("/api/field-missions/", { q: filters.q, kind: filters.kind, page, page_size: PAGE_SIZE })),
    [filters.q, filters.kind, page],
  )
  const columns: Column<FieldMission>[] = [
    { key: "kind", header: "النوع", render: (row) => row.kind },
    { key: "place", header: "المحل", render: (row) => row.place_name },
    { key: "phone", header: "الجوال", render: (row) => <bdi>{row.phone}</bdi> },
    { key: "where", header: "المكان", render: (row) => row.governorate_name },
    { key: "who", header: "المسؤولون", render: (row) => row.assignees.map((item) => item.name).filter(Boolean).join("، ") || "—" },
    { key: "when", header: "التسجيل", render: (row) => formatDateTime(row.created_at) },
  ]

  return (
    <div className="page">
      {canOpenMission(user) && (
        <div className="page__bar">
          <Button onClick={() => setCreating(true)}>مهمة جديدة</Button>
        </div>
      )}
      {creating && (
        <Dialog title="مهمة ميدانية" onClose={() => setCreating(false)}>
          <MissionForm
            user={user}
            onCancel={() => setCreating(false)}
            onSaved={(next) => {
              setCreating(false)
              setNotice(next)
              reload()
            }}
          />
        </Dialog>
      )}
      {open && (
        <Dialog title={open.place_name} onClose={() => setOpen(null)}>
          <MissionView mission={open} />
        </Dialog>
      )}
      <FilterBar
        schema={SCHEMA}
        onChange={(values) => {
          setFilters(values)
          setPage(1)
        }}
      />
      <NoticeLine notice={notice} />
      <Loaded state={state} onRetry={reload}>
        {(data) => (
          <DataTable
            caption="المهمات الميدانية"
            columns={columns}
            rows={data.results}
            getRowId={rowId}
            getRowLabel={(row) => row.place_name}
            emptyTitle="لا توجد مهمات ميدانية."
            rowActions={(row) => [{ id: "open", label: "عرض", onSelect: () => setOpen(row) }]}
            pagination={{ page: data.page, pageSize: data.page_size, total: data.count, onPageChange: setPage }}
          />
        )}
      </Loaded>
    </div>
  )
}
