import { useEffect, useState, type FormEvent } from "react"
import { Link, useParams } from "react-router-dom"
import { Button, FileField, Select, StatusChip, TextArea, TextField, Timeline, type TimelineEvent } from "../design-system"
import {
  apiRequest,
  apiUpload,
  postComplaintAction,
  withQuery,
  type ComplaintDetail,
  type Page,
  type SessionUser,
  type UserRow,
} from "../api"
import {
  ALL_ROWS,
  Loaded,
  NoticeLine,
  Section,
  actionNotice,
  failureText,
  fileName,
  formatDateTime,
  useLoad,
  type Notice,
} from "./common"

const MAX_FILES = 5

type ActionProps = { complaint: ComplaintDetail; onDone: (notice: Notice) => void }

function AcceptAction({ complaint, onDone }: ActionProps) {
  const [busy, setBusy] = useState(false)
  const onClick = async () => {
    setBusy(true)
    const result = await postComplaintAction("accept", [complaint.id])
    setBusy(false)
    onDone(actionNotice(result, "تم قبول الشكوى، وهي الآن قيد المتابعة الميدانية."))
  }
  return (
    <Section title="القبول" note="القبول نقرة واحدة. بعده تصير الشكوى قيد المتابعة الميدانية باسمك.">
      <div className="sheet__actions">
        <Button loading={busy} onClick={onClick}>
          قبول الشكوى
        </Button>
      </div>
    </Section>
  )
}

/** Inspectors can only be listed by admin. Any other role falls back to typing the inspector number. */
function useInspectorChoices(complaint: ComplaintDetail) {
  const [choices, setChoices] = useState<UserRow[] | null | undefined>(undefined)
  useEffect(() => {
    let cancelled = false
    apiRequest<Page<UserRow>>(withQuery("/api/users/", { role: "inspector", is_active: 1, page_size: ALL_ROWS })).then(
      (result) => {
        if (cancelled) return
        if (result.ok && result.data) setChoices(result.data.results.filter((u) => u.region === complaint.region))
        else setChoices(null)
      },
    )
    return () => {
      cancelled = true
    }
  }, [complaint.region])
  return choices
}

function AssignAction({ complaint, onDone }: ActionProps) {
  const choices = useInspectorChoices(complaint)
  const [inspector, setInspector] = useState("")
  const [error, setError] = useState<string | undefined>()
  const [busy, setBusy] = useState(false)

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const id = Number(inspector)
    if (!inspector || !Number.isInteger(id) || id < 1) {
      setError("اختر المفتش.")
      return
    }
    setError(undefined)
    setBusy(true)
    const result = await apiRequest(`/api/complaints/${complaint.id}/assign/`, { method: "POST", body: { inspector: id } })
    setBusy(false)
    onDone(result.ok ? { tone: "ok", text: "تم توجيه الشكوى إلى المفتش." } : { tone: "error", text: failureText(result) })
  }

  return (
    <Section title="التوجيه لمفتش" note={`المفتشون المفعّلون في ${complaint.region_name} فقط.`}>
      <form className="sheet__form" onSubmit={onSubmit} noValidate>
        {choices ? (
          <Select
            label="المفتش"
            name="inspector"
            placeholder={choices.length ? "اختر المفتش" : "لا يوجد مفتش مفعّل في هذه المنطقة"}
            options={choices.map((u) => ({ value: String(u.id), label: u.display_name || u.username }))}
            value={inspector}
            onChange={(e) => setInspector(e.target.value)}
            error={error}
            required
          />
        ) : choices === null ? (
          <TextField
            label="المفتش"
            name="inspector"
            type="number"
            min={1}
            inputMode="numeric"
            hint="رقم حساب المفتش."
            value={inspector}
            onChange={(e) => setInspector(e.target.value)}
            error={error}
            required
          />
        ) : null}
        <div className="sheet__actions">
          <Button type="submit" loading={busy} disabled={choices === undefined}>
            توجيه
          </Button>
        </div>
      </form>
    </Section>
  )
}

function FieldReportAction({ complaint, onDone }: ActionProps) {
  const [text, setText] = useState("")
  const [destination, setDestination] = useState("")
  const [files, setFiles] = useState<File[]>([])
  const [fileKey, setFileKey] = useState(0)
  const [errors, setErrors] = useState<{ text?: string; destination?: string; files?: string }>({})
  const [busy, setBusy] = useState(false)

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const found: typeof errors = {}
    if (!text.trim()) found.text = "اكتب تفاصيل الكشف."
    if (!destination) found.destination = "اختر جهة الإرسال."
    if (files.length > MAX_FILES) found.files = `الحد ${MAX_FILES} ملفات.`
    setErrors(found)
    if (Object.keys(found).length) return

    const form = new FormData()
    form.append("text", text.trim())
    form.append("body", text.trim())
    form.append("destination", destination)
    for (const file of files) form.append("files", file)
    setBusy(true)
    const result = await apiUpload(`/api/complaints/${complaint.id}/field-report/`, form)
    setBusy(false)
    if (result.ok) {
      setText("")
      setDestination("")
      setFiles([])
      setFileKey((k) => k + 1)
      onDone({ tone: "ok", text: "تم إرسال نتيجة الكشف." })
    } else {
      onDone({ tone: "error", text: failureText(result) })
    }
  }

  return (
    <Section title="نتيجة الكشف" note="التفاصيل مطلوبة. المرفقات اختيارية وبحد خمسة ملفات.">
      <form className="sheet__form" onSubmit={onSubmit} noValidate>
        <TextArea
          label="تفاصيل الكشف"
          name="text"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          error={errors.text}
          required
        />
        <Select
          label="الإرسال إلى"
          name="destination"
          placeholder="اختر الجهة"
          options={[
            { value: "governor", label: "مدير المحافظة وحده" },
            { value: "legal", label: "مدير المحافظة والشؤون القانونية" },
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
          hint="jpeg أو png أو webp أو pdf، بحد 5 ميغابايت للملف."
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          error={errors.files}
        />
        <div className="sheet__actions">
          <Button type="submit" loading={busy}>
            إرسال النتيجة
          </Button>
        </div>
      </form>
    </Section>
  )
}

function LegalCloseAction({ complaint, onDone }: ActionProps) {
  const [notes, setNotes] = useState("")
  const [busy, setBusy] = useState(false)
  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    const result = await apiRequest(`/api/complaints/${complaint.id}/legal-close/`, {
      method: "POST",
      body: { notes: notes.trim() },
    })
    setBusy(false)
    if (result.ok) setNotes("")
    onDone(result.ok ? { tone: "ok", text: "تم الانجاز وأُغلقت الشكوى." } : { tone: "error", text: failureText(result) })
  }
  return (
    <Section title="رد الشؤون القانونية" note="الملاحظات اختيارية.">
      <form className="sheet__form" onSubmit={onSubmit} noValidate>
        <TextArea label="الملاحظات" name="notes" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
        <div className="sheet__actions">
          <Button type="submit" loading={busy}>
            تم الانجاز
          </Button>
        </div>
      </form>
    </Section>
  )
}

function FlagAction({ complaint, onDone }: ActionProps) {
  const [busy, setBusy] = useState(false)
  const action = complaint.is_flagged ? "unflag" : "flag"
  const onClick = async () => {
    setBusy(true)
    const result = await postComplaintAction(action, [complaint.id])
    setBusy(false)
    onDone(actionNotice(result, action === "flag" ? "تم وضع علامة المتابعة." : "تمت إزالة علامة المتابعة."))
  }
  return (
    <Button variant="secondary" size="sm" loading={busy} onClick={onClick}>
      {complaint.is_flagged ? "إزالة علامة المتابعة" : "وضع علامة المتابعة"}
    </Button>
  )
}

function timelineFor(complaint: ComplaintDetail): TimelineEvent[] {
  const submitted: TimelineEvent = { id: "submitted", title: "تقديم الشكوى", at: formatDateTime(complaint.created_at) }
  return [
    submitted,
    ...complaint.follow_ups.map((line) => ({
      id: `follow-${line.id}`,
      title: line.place === "legal" ? "الشؤون القانونية" : "المتابعة الميدانية",
      at: formatDateTime(line.created_at),
      actor: line.author_name,
      body: (
        <>
          <p className="app-prose">{line.body}</p>
          {line.files.length > 0 && (
            <ul className="app-files" aria-label="المرفقات">
              {line.files.map((file) => (
                <li key={file.id}>
                  <a href={`/api/media/followups/${complaint.id}/${file.id}/`} target="_blank" rel="noreferrer">
                    {fileName(file.name)}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      ),
    })),
  ]
}

function ComplaintImage({ id }: { id: number }) {
  const [missing, setMissing] = useState(false)
  if (missing) return null
  return (
    <img className="dossier__image" src={`/api/media/complaints/${id}/`} alt="صورة الشكوى" onError={() => setMissing(true)} />
  )
}

function ComplaintView({ complaint, user, reload }: { complaint: ComplaintDetail; user: SessionUser; reload: () => void }) {
  const [notice, setNotice] = useState<Notice>(null)
  const onDone = (next: Notice) => {
    setNotice(next)
    reload()
  }
  const status = complaint.status
  const props = { complaint, onDone }
  const canFlag = user.role === "admin" || (user.role === "governor" && user.governorate === complaint.governorate)
  const actions = [
    user.role === "inspector" && status === "واردة" && <AcceptAction key="accept" {...props} />,
    user.role === "governor" && status === "واردة" && <AssignAction key="assign" {...props} />,
    user.role === "inspector" && status === "قيد المتابعة الميدانية" && complaint.inspector === user.id && (
      <FieldReportAction key="field" {...props} />
    ),
    user.role === "legal" && status === "قيد المتابعة في الشؤون القانونية" && <LegalCloseAction key="legal" {...props} />,
  ].filter(Boolean)

  return (
    <div className="page">
      <p className="app-back">
        <Link className="app-link" to="/complaints/">
          العودة إلى الشكاوى
        </Link>
      </p>
      <article className="dossier" aria-label={`الشكوى رقم ${complaint.id}`}>
        <header className="dossier__head">
          <span className="dossier__number">رقم {complaint.id}</span>
          <h2 className="dossier__title">{complaint.title}</h2>
          <StatusChip status={status} />
          {complaint.is_flagged && <span className="app-flag">عليها علامة المتابعة</span>}
          {canFlag && <FlagAction {...props} />}
        </header>
        <dl className="dossier__meta">
          <div>
            <dt>المحافظة</dt>
            <dd>{complaint.governorate_name}</dd>
          </div>
          <div>
            <dt>المنطقة</dt>
            <dd>{complaint.region_name}</dd>
          </div>
          <div>
            <dt>المفتش المستلم</dt>
            <dd>{complaint.inspector_name || "—"}</dd>
          </div>
          <div>
            <dt>وقت التقديم</dt>
            <dd>{formatDateTime(complaint.created_at)}</dd>
          </div>
        </dl>
        <p className="app-prose dossier__body">{complaint.body}</p>
        <ComplaintImage id={complaint.id} />
      </article>
      <NoticeLine notice={notice} />
      {actions}
      <Section title="خط التقدم" note="من الأقدم إلى الأحدث.">
        <Timeline events={timelineFor(complaint)} label="خط تقدم الشكوى" />
      </Section>
    </div>
  )
}

export function ComplaintPage({ user }: { user: SessionUser }) {
  const { id = "" } = useParams()
  const { state, reload } = useLoad(() => apiRequest<ComplaintDetail>(`/api/complaints/${id}/`), [id])
  return (
    <Loaded state={state} onRetry={reload}>
      {(complaint) => <ComplaintView complaint={complaint} user={user} reload={reload} />}
    </Loaded>
  )
}
