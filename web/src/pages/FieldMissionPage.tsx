import { useEffect, useState, type FormEvent } from "react"
import { Link, useParams } from "react-router-dom"
import { Button, FileField, Select, StatusChip, TextArea, Timeline, type TimelineEvent } from "../design-system"
import { apiRequest, apiUpload, withQuery, type FieldMission, type FollowUpLine, type Page, type SessionUser, type UserRow } from "../api"
import { Loaded, NoticeLine, Section, failureText, fileName, formatDateTime, useLoad, type Notice } from "./common"
import { PriorityChip, peopleOf } from "./FieldMissionsPage"

const PLACE_TITLE: Record<string, string> = { route: "إعادة التوجيه", field: "الرد الميداني", legal: "الشؤون القانونية" }
const MAX_FILES = 5

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

function MissionView({ mission, user, reload }: { mission: FieldMission; user: SessionUser; reload: () => void }) {
  const [notice, setNotice] = useState<Notice>(null)
  const assigned = mission.assignees.some((row) => row.id === user.id)
  const onDone = (next: Notice) => {
    setNotice(next)
    reload()
  }
  const place = [mission.governorate_name, mission.region_name].filter(Boolean).join("، ")
  const facts: { label: string; value: string; ltr?: boolean }[] = [
    { label: "النوع", value: mission.kind },
    { label: "المكان", value: place || "غير محدد" },
    { label: "الجوال", value: mission.phone, ltr: true },
    { label: "المسؤولون", value: peopleOf(mission) },
    { label: "فتحها", value: `${mission.created_by_name || "—"} · ${formatDateTime(mission.created_at)}` },
  ]
  if (mission.field_replied_at) facts.push({ label: "وقت الرد الميداني", value: formatDateTime(mission.field_replied_at) })
  if (mission.legal_referred_at) facts.push({ label: "إحالة الشؤون القانونية", value: formatDateTime(mission.legal_referred_at) })
  if (mission.closed_at) facts.push({ label: "وقت الإغلاق", value: formatDateTime(mission.closed_at) })

  return (
    <div className="page">
      <p className="app-back">
        <Link className="app-link" to="/field-missions/">
          العودة إلى المهمات الميدانية
        </Link>
      </p>
      <article className="dossier" aria-label={`مهمة ${mission.id}`}>
        <header className="dossier__head">
          <div className="dossier__idline">
            <PriorityChip priority={mission.priority} />
            <StatusChip status={mission.status} />
            <span className="dossier__number">مهمة {mission.id}</span>
          </div>
          <h2 className="dossier__title">{mission.place_name}</h2>
        </header>
        <section className="dossier__story" aria-label="تفاصيل المهمة">
          <h3 className="dossier__kicker">تفاصيل المهمة</h3>
          <p className="app-prose dossier__body">{mission.details}</p>
          {mission.has_image && <img className="dossier__image" src={`/api/media/field-missions/${mission.id}/`} alt={mission.place_name} />}
        </section>
        <dl className="dossier__facts" aria-label="بيانات المهمة">
          {facts.map((fact) => (
            <div key={fact.label}>
              <dt>{fact.label}</dt>
              <dd>{fact.ltr ? <bdi dir="ltr">{fact.value}</bdi> : fact.value}</dd>
            </div>
          ))}
        </dl>
      </article>
      <NoticeLine notice={notice} />
      {user.role === "governor" && mission.status === "عند إدارة المحافظة" && (
        <Section title="إعادة التوجيه" note="مرة واحدة، لمفتش مفعّل في المحافظة.">
          <RedirectForm mission={mission} onDone={onDone} />
        </Section>
      )}
      {user.role === "inspector" && assigned && mission.status === "قيد المتابعة الميدانية" && (
        <Section title="الرد" note="النص مطلوب. اختر إنهاء المهمة أو إحالتها للشؤون القانونية.">
          <ReplyForm mission={mission} onDone={onDone} />
        </Section>
      )}
      {user.role === "legal" && mission.status === "قيد المتابعة في الشؤون القانونية" && (
        <Section title="الشؤون القانونية" note="الإغلاق ينقل المهمة إلى تم المعالجة.">
          <CloseForm mission={mission} onDone={onDone} />
        </Section>
      )}
      <Section title="خط التقدم" note="من الأقدم إلى الأحدث.">
        <Timeline events={eventsOf(mission)} label="سجل حركة المهمة" />
      </Section>
    </div>
  )
}

export function FieldMissionPage({ user }: { user: SessionUser }) {
  const { id = "" } = useParams()
  const { state, reload } = useLoad(() => apiRequest<FieldMission>(`/api/field-missions/${id}/`), [id])
  return (
    <Loaded state={state} onRetry={reload}>
      {(mission) => <MissionView mission={mission} user={user} reload={reload} />}
    </Loaded>
  )
}
