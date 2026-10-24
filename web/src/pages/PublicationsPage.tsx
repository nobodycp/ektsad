import { useState, type FormEvent } from "react"
import { Button, DataTable, FileField, TextArea, type Column } from "../design-system"
import { apiRequest, apiUpload, withQuery, type Page, type Publication, type SessionUser } from "../api"
import { Loaded, NoticeLine, PAGE_SIZE, Section, failureText, formatDateTime, useLoad, type Notice } from "./common"
import { NO_CROSSINGS, NO_PRICES } from "./PublicPage"

type Kind = "prices" | "crossings"

const COPY = {
  prices: {
    flag: "can_publish_prices",
    form: "نشر قائمة أسعار",
    formNote: "الصورة مطلوبة. كل نشر سطر جديد، والصفحة العامة تعرض الأحدث فقط.",
    current: "القائمة المعروضة للزائر",
    empty: NO_PRICES,
    media: "/api/media/prices/latest/",
    done: "تم نشر قائمة الأسعار.",
  },
  crossings: {
    flag: "can_publish_crossings",
    form: "نشر حركة المعابر",
    formNote: "نص أو صورة أو كلاهما. كل نشر سطر جديد، والصفحة العامة تعرض الأحدث فقط.",
    current: "الحركة المعروضة للزائر",
    empty: NO_CROSSINGS,
    media: "/api/media/crossings/latest/",
    done: "تم نشر حركة المعابر.",
  },
} as const

const rowId = (row: Publication) => row.id

function PublishForm({ kind, onDone }: { kind: Kind; onDone: (notice: Notice) => void }) {
  const copy = COPY[kind]
  const [body, setBody] = useState("")
  const [image, setImage] = useState<File | null>(null)
  const [fileKey, setFileKey] = useState(0)
  const [error, setError] = useState<string | undefined>()
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice(null)
    if (kind === "prices" && !image) return setError("اختر صورة القائمة.")
    if (kind === "crossings" && !image && !body.trim()) return setError("اكتب النص أو أرفق صورة.")
    setError(undefined)
    const form = new FormData()
    if (kind === "crossings") form.append("body", body.trim())
    if (image) form.append("image", image)
    setBusy(true)
    const result = await apiUpload(`/api/${kind}/`, form)
    setBusy(false)
    if (result.ok) {
      setBody("")
      setImage(null)
      setFileKey((k) => k + 1)
      onDone({ tone: "ok", text: copy.done })
    } else {
      setNotice({ tone: "error", text: failureText(result) })
    }
  }

  return (
    <Section title={copy.form} note={copy.formNote}>
      <form className="sheet__form" onSubmit={onSubmit} noValidate>
        {kind === "crossings" && (
          <TextArea label="نص الحركة" name="body" rows={4} value={body} onChange={(e) => setBody(e.target.value)} />
        )}
        <FileField
          key={fileKey}
          label={kind === "prices" ? "صورة القائمة" : "صورة"}
          name="image"
          accept="image/jpeg,image/png,image/webp"
          hint="jpeg أو png أو webp بحد 5 ميغابايت."
          required={kind === "prices"}
          error={error}
          onChange={(e) => setImage(e.target.files?.[0] ?? null)}
        />
        <NoticeLine notice={notice} />
        <div className="sheet__actions">
          <Button type="submit" loading={busy}>
            نشر
          </Button>
        </div>
      </form>
    </Section>
  )
}

export function PublicationsPage({ kind, user }: { kind: Kind; user: SessionUser }) {
  const copy = COPY[kind]
  const [page, setPage] = useState(1)
  const [notice, setNotice] = useState<Notice>(null)
  const canPublish = Boolean(user[copy.flag])

  const { state, reload } = useLoad(
    () => apiRequest<Page<Publication>>(withQuery(`/api/${kind}/`, { page, page_size: PAGE_SIZE })),
    [kind, page],
  )

  const columns: Column<Publication>[] = [
    { key: "published_at", header: "وقت النشر", render: (row) => formatDateTime(row.published_at) },
    { key: "publisher", header: "الناشر", render: (row) => row.publisher_name || "—" },
  ]
  if (kind === "crossings") columns.push({ key: "body", header: "النص", render: (row) => row.body || "—" })
  columns.push({ key: "image", header: "صورة", render: (row) => (row.has_image ? "مرفقة" : "—") })

  return (
    <div className="page">
      {canPublish && (
        <PublishForm
          kind={kind}
          onDone={(next) => {
            setNotice(next)
            setPage(1)
            reload()
          }}
        />
      )}
      <NoticeLine notice={notice} />
      <Loaded state={state} onRetry={reload}>
        {(data) => {
          const newest = data.page === 1 ? data.results[0] : undefined
          return (
            <>
              {newest?.has_image && (
                <Section title={copy.current} note={`نُشرت في ${formatDateTime(newest.published_at)}`}>
                  <img className="sheet__image" src={`${copy.media}?v=${newest.id}`} alt={copy.current} />
                </Section>
              )}
              <DataTable
                caption={copy.form}
                columns={columns}
                rows={data.results}
                getRowId={rowId}
                emptyTitle={copy.empty}
                pagination={{ page: data.page, pageSize: data.page_size, total: data.count, onPageChange: setPage }}
              />
            </>
          )
        }}
      </Loaded>
    </div>
  )
}
