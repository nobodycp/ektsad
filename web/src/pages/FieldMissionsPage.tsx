import { useEffect, useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import {
  Button,
  DataTable,
  Dialog,
  FileField,
  FilterBar,
  Select,
  StatusChip,
  TextArea,
  TextField,
  type Column,
  type FilterField,
  type FilterValues,
  type TimelineEvent,
} from "../design-system"
import { apiRequest, apiUpload, withQuery, type FieldMission, type Page, type SessionUser, type UserRow } from "../api"
import { Loaded, NoticeLine, PAGE_SIZE, failureText, formatDateTime, useLoad, type Notice } from "./common"
import { optionsOf, useAdminGeography } from "./geo"

export const MISSION_KINDS = ["ضبط", "تحفظ", "إثبات حالة", "مصادرة", "إتلاف", "عينات فحص", "أخرى"] as const
export const MISSION_PRIORITIES = ["خطر", "عاجل", "متوسط", "عادي"] as const

const KIND_OPTIONS = MISSION_KINDS.map((kind) => ({ value: kind, label: kind }))
const PRIORITY_OPTIONS = MISSION_PRIORITIES.map((priority) => ({ value: priority, label: priority }))
const PRIORITY_TONE: Record<string, string> = { خطر: "danger", عاجل: "field", متوسط: "legal", عادي: "incoming" }
const SCHEMA: FilterField[] = [
  { type: "search", key: "q", label: "بحث", placeholder: "اسم المحل" },
  { type: "select", key: "kind", label: "نوع المهمة", options: KIND_OPTIONS },
]

const rowId = (row: FieldMission) => row.id

export function canOpenMission(user: SessionUser) {
  if (user.role === "admin") return true
  if (user.role === "legal") return false
  if (user.role === "custom" || user.role === "governor" || user.role === "inspector") return Boolean(user.can_open_field_missions)
  return false
}

function opensNationally(user: SessionUser) {
  return user.role === "admin" || user.role === "custom"
}

export function PriorityChip({ priority }: { priority: string }) {
  return (
    <span className="ds-chip" data-tone={PRIORITY_TONE[priority] ?? "unknown"}>
      {priority}
    </span>
  )
}

export function peopleOf(mission: FieldMission) {
  const names = mission.assignees.map((row) => row.name).filter(Boolean).join("، ")
  if (names) return names
  return mission.status === "عند إدارة المحافظة" ? "إدارة المحافظة" : "—"
}

function MissionForm({ user, onSaved, onCancel }: { user: SessionUser; onSaved: (notice: Notice) => void; onCancel: () => void }) {
  const geo = useAdminGeography()
  const [kind, setKind] = useState("")
  const [priority, setPriority] = useState("")
  const [details, setDetails] = useState("")
  const [placeName, setPlaceName] = useState("")
  const [phone, setPhone] = useState("")
  const [image, setImage] = useState<File | null>(null)
  const [governorate, setGovernorate] = useState("")
  const [scope, setScope] = useState<"one" | "all" | "office">("one")
  const [inspector, setInspector] = useState("")
  const [inspectors, setInspectors] = useState<UserRow[]>([])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)
  const national = opensNationally(user)
  const assigns = national || user.role === "governor"
  const governorateId = user.role === "governor" ? user.governorate : Number(governorate) || null
  const scopeOptions = [
    { value: "one", label: "مفتش واحد" },
    { value: "all", label: "كل المفتشين" },
    ...(national ? [{ value: "office", label: "إدارة المحافظة" }] : []),
  ]

  useEffect(() => {
    if (!assigns || !governorateId || scope === "office") {
      setInspectors([])
      return
    }
    let cancelled = false
    const query = national ? { governorate: governorateId } : {}
    apiRequest<Page<UserRow>>(withQuery("/api/users/", { role: "inspector", is_active: "1", page_size: 100, ...query })).then((result) => {
      if (!cancelled) setInspectors(result.data?.results ?? [])
    })
    return () => {
      cancelled = true
    }
  }, [assigns, governorateId, national, scope])

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const found: Record<string, string> = {}
    if (!kind) found.kind = "اختر نوع المهمة."
    if (!priority) found.priority = "اختر أولوية المهمة."
    if (!details.trim()) found.details = "التفاصيل مطلوبة."
    if (!placeName.trim()) found.place_name = "اسم المحل مطلوب."
    if (!phone.trim()) found.phone = "رقم الجوال مطلوب."
    if (national && !governorate) found.governorate = "اختر المحافظة."
    if (assigns && scope === "one" && !inspector) found.inspector = "اختر المفتش."
    setErrors(found)
    if (Object.keys(found).length) return
    const form = new FormData()
    form.set("kind", kind)
    form.set("priority", priority)
    form.set("details", details.trim())
    form.set("place_name", placeName.trim())
    form.set("phone", phone.trim())
    if (image) form.set("image", image)
    if (national) form.set("governorate", governorate)
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
        <Select label="الأولوية" name="priority" placeholder="اختر الأولوية" options={PRIORITY_OPTIONS} value={priority} onChange={(e) => setPriority(e.target.value)} error={errors.priority} required />
        <TextArea label="تفاصيل المهمة" name="details" rows={4} value={details} onChange={(e) => setDetails(e.target.value)} error={errors.details} required />
        <TextField label="اسم المحل" name="place_name" value={placeName} onChange={(e) => setPlaceName(e.target.value)} error={errors.place_name} required />
        <TextField label="رقم الجوال" name="phone" value={phone} onChange={(e) => setPhone(e.target.value)} error={errors.phone} required dir="ltr" />
        <FileField label="صورة" name="image" accept="image/jpeg,image/png,image/webp" hint="اختيارية. jpeg أو png أو webp بحد 5 ميغابايت." onChange={(e) => setImage(e.target.files?.[0] ?? null)} />
        {national && (
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
          <Select label="التوجيه" name="scope" options={scopeOptions} value={scope} onChange={(e) => setScope(e.target.value as "one" | "all" | "office")} />
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

export function FieldMissionsPage({ user }: { user: SessionUser }) {
  const [filters, setFilters] = useState<FilterValues>({})
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  const { state, reload } = useLoad(
    () => apiRequest<Page<FieldMission>>(withQuery("/api/field-missions/", { q: filters.q, kind: filters.kind, page, page_size: PAGE_SIZE })),
    [filters.q, filters.kind, page],
  )
  const columns: Column<FieldMission>[] = [
    { key: "kind", header: "النوع", render: (row) => row.kind },
    { key: "priority", header: "الأولوية", render: (row) => <PriorityChip priority={row.priority} /> },
    { key: "status", header: "الحالة", render: (row) => <StatusChip status={row.status} /> },
    {
      key: "place",
      header: "المحل",
      render: (row) => (
        <Link className="app-link" to={`/field-missions/${row.id}/`}>
          {row.place_name}
        </Link>
      ),
    },
    { key: "phone", header: "الجوال", render: (row) => <bdi>{row.phone}</bdi> },
    { key: "where", header: "المكان", render: (row) => row.governorate_name },
    { key: "who", header: "المسؤولون", render: (row) => peopleOf(row) },
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
            pagination={{ page: data.page, pageSize: data.page_size, total: data.count, onPageChange: setPage }}
          />
        )}
      </Loaded>
    </div>
  )
}
