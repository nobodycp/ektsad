import { useEffect, useState, type FormEvent } from "react"
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
  Timeline,
  type Column,
  type FilterField,
  type FilterValues,
  type TimelineEvent,
} from "../design-system"
import { apiRequest, apiUpload, withQuery, type FieldMission, type FollowUpLine, type Page, type SessionUser, type UserRow } from "../api"
import { Loaded, NoticeLine, PAGE_SIZE, failureText, fileName, formatDateTime, useLoad, type Notice } from "./common"
import { optionsOf, useAdminGeography } from "./geo"

export const MISSION_KINDS = ["ضبط", "تحفظ", "إثبات حالة", "مصادرة", "إتلاف", "عينات فحص", "أخرى"] as const
export const MISSION_PRIORITIES = ["خطر", "عاجل", "متوسط", "عادي"] as const

const KIND_OPTIONS = MISSION_KINDS.map((kind) => ({ value: kind, label: kind }))
const PRIORITY_OPTIONS = MISSION_PRIORITIES.map((priority) => ({ value: priority, label: priority }))
const PRIORITY_TONE: Record<string, string> = { خطر: "danger", عاجل: "field", متوسط: "legal", عادي: "incoming" }
const PLACE_TITLE: Record<string, string> = { route: "إعادة التوجيه", field: "الرد الميداني", legal: "الشؤون القانونية" }
const MAX_FILES = 5

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

function PriorityChip({ priority }: { priority: string }) {
  return (
    <span className="ds-chip" data-tone={PRIORITY_TONE[priority] ?? "unknown"}>
      {priority}
    </span>
  )
}

function peopleOf(mission: FieldMission) {
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
  const assigns = user.role === "admin" || user.role === "governor"
  const governorateId = user.role === "governor" ? user.governorate : Number(governorate) || null
  const scopeOptions = [
    { value: "one", label: "مفتش واحد" },
    { value: "all", label: "كل المفتشين" },
    ...(user.role === "admin" ? [{ value: "office", label: "إدارة المحافظة" }] : []),
  ]

  useEffect(() => {
    if (!assigns || !governorateId || scope === "office") {
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
  }, [assigns, governorateId, scope, user.role])

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const found: Record<string, string> = {}
    if (!kind) found.kind = "اختر نوع المهمة."
    if (!priority) found.priority = "اختر أولوية المهمة."
    if (!details.trim()) found.details = "التفاصيل مطلوبة."
    if (!placeName.trim()) found.place_name = "اسم المحل مطلوب."
    if (!phone.trim()) found.phone = "رقم الجوال مطلوب."
    if (user.role === "admin" && !governorate) found.governorate = "اختر المحافظة."
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
        <Select label="الأولوية" name="priority" placeholder="اختر الأولوية" options={PRIORITY_OPTIONS} value={priority} onChange={(e) => setPriority(e.target.value)} error={errors.priority} required />
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

function eventsOf(mission: FieldMission): TimelineEvent[] {
  const opened: TimelineEvent = {
    id: "opened",
    title: "فتح المهمة",
    at: formatDateTime(mission.created_at),
    actor: mission.created_by_name || undefined,
    body: <p className="app-prose">{mission.details}</p>,
  }
  const lines = (mission.follow_ups ?? []).map((line: FollowUpLine) => ({
    id: `follow-${line.id}`,
    title: PLACE_TITLE[line.place] ?? line.place,
    at: formatDateTime(line.created_at),
    actor: line.author_name,
    body: (
      <>
        <p className="app-prose">{line.body}</p>
        {line.files.length > 0 && (
          <ul className="app-files" aria-label="المرفقات">
            {line.files.map((file) => (
              <li key={file.id}>
                <a href={`/api/media/field-missions/${mission.id}/followups/${file.id}/`} target="_blank" rel="noreferrer">
                  {fileName(file.name)}
                </a>
              </li>
            ))}
          </ul>
        )}
      </>
    ),
  }))
  return [opened, ...lines]
}

function RedirectForm({ mission, onDone }: { mission: FieldMission; onDone: (notice: Notice) => void }) {
  const [inspector, setInspector] = useState("")
  const [inspectors, setInspectors] = useState<UserRow[]>([])
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiRequest<Page<UserRow>>(withQuery("/api/users/", { role: "inspector", is_active: "1", page_size: 100 })).then((result) => {
      if (!cancelled) setInspectors(result.data?.results ?? [])
    })
    return () => {
      cancelled = true
    }
  }, [])

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!inspector) {
      setError("اختر المفتش.")
      return
    }
    setBusy(true)
    const result = await apiRequest(`/api/field-missions/${mission.id}/redirect/`, { method: "POST", body: { inspector: Number(inspector) } })
    setBusy(false)
    if (result.ok) onDone({ tone: "ok", text: "تم توجيه المهمة إلى المفتش." })
    else onDone({ tone: "error", text: failureText(result) })
  }

  return (
    <form className="sheet__form" onSubmit={onSubmit} noValidate>
      <Select
        label="المفتش"
        name="inspector"
        placeholder="اختر المفتش"
        options={inspectors.map((row) => ({ value: String(row.id), label: row.display_name || row.username }))}
        value={inspector}
        onChange={(e) => setInspector(e.target.value)}
        error={error}
        required
      />
      <div className="sheet__actions">
        <Button type="submit" loading={busy}>
          إعادة التوجيه
        </Button>
      </div>
    </form>
  )
}

function ReplyForm({ mission, onDone }: { mission: FieldMission; onDone: (notice: Notice) => void }) {
  const [text, setText] = useState("")
  const [destination, setDestination] = useState("")
  const [files, setFiles] = useState<File[]>([])
  const [fileKey, setFileKey] = useState(0)
  const [errors, setErrors] = useState<{ text?: string; destination?: string; files?: string }>({})
  const [busy, setBusy] = useState(false)

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const found: typeof errors = {}
    if (!text.trim()) found.text = "نص الرد مطلوب."
    if (!destination) found.destination = "اختر نتيجة المهمة."
    if (files.length > MAX_FILES) found.files = "الحد الأقصى خمسة ملفات."
    setErrors(found)
    if (Object.keys(found).length) return
    const form = new FormData()
    form.set("text", text.trim())
    form.set("destination", destination)
    for (const file of files) form.append("files", file)
    setBusy(true)
    const result = await apiUpload(`/api/field-missions/${mission.id}/reply/`, form)
    setBusy(false)
    if (!result.ok) {
      onDone({ tone: "error", text: failureText(result) })
      return
    }
    setText("")
    setDestination("")
    setFiles([])
    setFileKey((key) => key + 1)
    onDone({ tone: "ok", text: destination === "legal" ? "أُرسلت المهمة إلى الشؤون القانونية." : "تم إنهاء المهمة." })
  }

  return (
    <form className="sheet__form" onSubmit={onSubmit} noValidate>
      <TextArea label="الرد" name="text" rows={4} value={text} onChange={(e) => setText(e.target.value)} error={errors.text} required />
      <Select
        label="النتيجة"
        name="destination"
        placeholder="اختر النتيجة"
        options={[
          { value: "finished", label: "منتهية" },
          { value: "legal", label: "للشؤون القانونية" },
        ]}
        value={destination}
        onChange={(e) => setDestination(e.target.value)}
        error={errors.destination}
        required
      />
      <FileField
        key={fileKey}
        label="المرفقات"
        name="files"
        multiple
        accept="image/jpeg,image/png,image/webp,application/pdf"
        hint="حتى خمسة ملفات. jpeg أو png أو webp أو pdf، بحد 5 ميغابايت للملف."
        onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        error={errors.files}
      />
      <div className="sheet__actions">
        <Button type="submit" loading={busy}>
          إرسال الرد
        </Button>
      </div>
    </form>
  )
}

function CloseForm({ mission, onDone }: { mission: FieldMission; onDone: (notice: Notice) => void }) {
  const [notes, setNotes] = useState("")
  const [busy, setBusy] = useState(false)
  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    const result = await apiRequest(`/api/field-missions/${mission.id}/close/`, { method: "POST", body: { notes: notes.trim() } })
    setBusy(false)
    onDone(result.ok ? { tone: "ok", text: "تم المعالجة." } : { tone: "error", text: failureText(result) })
  }
  return (
    <form className="sheet__form" onSubmit={onSubmit} noValidate>
      <TextArea label="الملاحظات" name="notes" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
      <div className="sheet__actions">
        <Button type="submit" loading={busy}>
          تم المعالجة
        </Button>
      </div>
    </form>
  )
}

function MissionBody({ mission, user, onChanged }: { mission: FieldMission; user: SessionUser; onChanged: () => void }) {
  const [notice, setNotice] = useState<Notice>(null)
  const assigned = mission.assignees.some((row) => row.id === user.id)
  const onDone = (next: Notice) => {
    setNotice(next)
    onChanged()
  }
  return (
    <div className="sheet__form">
      <div className="sheet__grid">
        <p><span className="ds-field__label">النوع</span><br />{mission.kind}</p>
        <p><span className="ds-field__label">الأولوية</span><br /><PriorityChip priority={mission.priority} /></p>
        <p><span className="ds-field__label">الحالة</span><br /><StatusChip status={mission.status} /></p>
        <p><span className="ds-field__label">المحل</span><br />{mission.place_name}</p>
        <p><span className="ds-field__label">الجوال</span><br /><bdi>{mission.phone}</bdi></p>
        <p><span className="ds-field__label">المكان</span><br />{mission.governorate_name}{mission.region_name ? `، ${mission.region_name}` : ""}</p>
        <p><span className="ds-field__label">المسؤولون</span><br />{peopleOf(mission)}</p>
      </div>
      {mission.has_image && <img className="ds-mission-photo" src={`/api/media/field-missions/${mission.id}/`} alt={mission.place_name} />}
      <Timeline events={eventsOf(mission)} label="سجل الحركة" />
      <NoticeLine notice={notice} />
      {user.role === "governor" && mission.status === "عند إدارة المحافظة" && <RedirectForm mission={mission} onDone={onDone} />}
      {user.role === "inspector" && assigned && mission.status === "قيد المتابعة الميدانية" && <ReplyForm mission={mission} onDone={onDone} />}
      {user.role === "legal" && mission.status === "قيد المتابعة في الشؤون القانونية" && <CloseForm mission={mission} onDone={onDone} />}
    </div>
  )
}

function MissionView({ missionId, user, onChanged }: { missionId: number; user: SessionUser; onChanged: () => void }) {
  const { state, reload } = useLoad(() => apiRequest<FieldMission>(`/api/field-missions/${missionId}/`), [missionId])
  return (
    <Loaded state={state} onRetry={reload}>
      {(mission) => <MissionBody mission={mission} user={user} onChanged={() => { onChanged(); reload() }} />}
    </Loaded>
  )
}

export function FieldMissionsPage({ user }: { user: SessionUser }) {
  const [filters, setFilters] = useState<FilterValues>({})
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const [openId, setOpenId] = useState<number | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const { state, reload } = useLoad(
    () => apiRequest<Page<FieldMission>>(withQuery("/api/field-missions/", { q: filters.q, kind: filters.kind, page, page_size: PAGE_SIZE })),
    [filters.q, filters.kind, page],
  )
  const columns: Column<FieldMission>[] = [
    { key: "kind", header: "النوع", render: (row) => row.kind },
    { key: "priority", header: "الأولوية", render: (row) => <PriorityChip priority={row.priority} /> },
    { key: "status", header: "الحالة", render: (row) => <StatusChip status={row.status} /> },
    { key: "place", header: "المحل", render: (row) => row.place_name },
    { key: "phone", header: "الجوال", render: (row) => <bdi>{row.phone}</bdi> },
    { key: "where", header: "المكان", render: (row) => row.governorate_name },
    { key: "who", header: "المسؤولون", render: (row) => peopleOf(row) },
    { key: "when", header: "التسجيل", render: (row) => formatDateTime(row.created_at) },
  ]
  const openMission = state.status === "ready" ? state.data.results.find((row) => row.id === openId) : undefined

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
      {openId != null && (
        <Dialog title={openMission?.place_name ?? "المهمة الميدانية"} onClose={() => setOpenId(null)}>
          <MissionView missionId={openId} user={user} onChanged={reload} />
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
            rowActions={(row) => [{ id: "open", label: "عرض", onSelect: () => setOpenId(row.id) }]}
            pagination={{ page: data.page, pageSize: data.page_size, total: data.count, onPageChange: setPage }}
          />
        )}
      </Loaded>
    </div>
  )
}
