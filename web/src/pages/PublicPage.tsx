import { useEffect, useState, type FormEvent } from "react"
import { Button, FileField, LoadingState, Select, TextArea, TextField } from "../design-system"
import {
  apiRequest,
  apiUpload,
  ensureCsrfCookie,
  withQuery,
  type Page,
  type Place,
  type Publication,
  type RegionPlace,
} from "../api"
import { ALL_ROWS, NoticeLine, failureText, formatDateTime, type Notice } from "./common"

export const COMPLAINT_RECEIVED = "تم استلام الشكوى."
export const NO_PRICES = "لا توجد قائمة أسعار منشورة."
export const NO_CROSSINGS = "لا توجد حركة معابر منشورة."

type Latest = { status: "loading" } | { status: "none"; text: string } | { status: "ready"; item: Publication }

function useLatest(path: string, emptyText: string): Latest {
  const [latest, setLatest] = useState<Latest>({ status: "loading" })
  useEffect(() => {
    let cancelled = false
    apiRequest<Partial<Publication> & { detail?: string }>(path).then((result) => {
      if (cancelled) return
      const data = result.data
      if (result.ok && data && typeof data.id === "number") setLatest({ status: "ready", item: data as Publication })
      else setLatest({ status: "none", text: emptyText })
    })
    return () => {
      cancelled = true
    }
  }, [path, emptyText])
  return latest
}

type Errors = Partial<Record<"governorate" | "region" | "title" | "body", string>>

export function ComplaintForm({ onSubmitted }: { onSubmitted?: () => void } = {}) {
  const [governorates, setGovernorates] = useState<Place[]>([])
  const [regions, setRegions] = useState<RegionPlace[]>([])
  const [governorate, setGovernorate] = useState("")
  const [region, setRegion] = useState("")
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [image, setImage] = useState<File | null>(null)
  const [fileKey, setFileKey] = useState(0)
  const [errors, setErrors] = useState<Errors>({})
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    apiRequest<Page<Place>>(withQuery("/api/governorates/public/", { page_size: ALL_ROWS })).then((result) => {
      if (result.ok && result.data) setGovernorates(result.data.results)
    })
  }, [])

  useEffect(() => {
    setRegions([])
    if (!governorate) return
    let cancelled = false
    apiRequest<Page<RegionPlace>>(withQuery("/api/regions/public/", { governorate, page_size: ALL_ROWS })).then(
      (result) => {
        if (!cancelled && result.ok && result.data) setRegions(result.data.results)
      },
    )
    return () => {
      cancelled = true
    }
  }, [governorate])

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice(null)
    const found: Errors = {}
    if (!governorate) found.governorate = "اختر المحافظة."
    if (!region) found.region = "اختر المنطقة."
    if (!title.trim()) found.title = "اكتب عنوان الشكوى."
    if (!body.trim()) found.body = "اكتب نص الشكوى."
    setErrors(found)
    if (Object.keys(found).length) return

    const form = new FormData()
    form.append("governorate", governorate)
    form.append("region", region)
    form.append("title", title.trim())
    form.append("body", body.trim())
    if (image) form.append("image", image)
    setBusy(true)
    await ensureCsrfCookie()
    const result = await apiUpload("/api/complaints/public/", form)
    setBusy(false)
    if (result.status === 201) {
      setGovernorate("")
      setRegion("")
      setTitle("")
      setBody("")
      setImage(null)
      setFileKey((k) => k + 1)
      if (onSubmitted) {
        onSubmitted()
        return
      }
      setNotice({ tone: "ok", text: COMPLAINT_RECEIVED })
      return
    }
    setNotice({ tone: "error", text: failureText(result, "تعذّر إرسال الشكوى. أعد المحاولة.") })
  }

  return (
    <form className="public__form" onSubmit={onSubmit} noValidate>
      <div className="public__pair">
        <Select
          label="المحافظة"
          name="governorate"
          placeholder="اختر المحافظة"
          options={governorates.map((g) => ({ value: String(g.id), label: g.name }))}
          value={governorate}
          onChange={(e) => {
            setGovernorate(e.target.value)
            setRegion("")
          }}
          error={errors.governorate}
          required
        />
        <Select
          label="المنطقة"
          name="region"
          placeholder={governorate ? "اختر المنطقة" : "اختر المحافظة أولاً"}
          options={regions.map((r) => ({ value: String(r.id), label: r.name }))}
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          disabled={!governorate}
          error={errors.region}
          required
        />
      </div>
      <TextField
        label="عنوان الشكوى"
        name="title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        error={errors.title}
        required
      />
      <TextArea
        label="محتوى الشكوى"
        name="body"
        rows={6}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        error={errors.body}
        required
      />
      <FileField
        key={fileKey}
        label="صورة"
        name="image"
        accept="image/jpeg,image/png,image/webp"
        hint="اختيارية. jpeg أو png أو webp بحد 5 ميغابايت."
        onChange={(e) => setImage(e.target.files?.[0] ?? null)}
      />
      <NoticeLine notice={notice} />
      <div className="public__actions">
        <Button type="submit" loading={busy}>
          تقديم الشكوى
        </Button>
      </div>
    </form>
  )
}

function Bulletin({ latest, mediaPath, alt }: { latest: Latest; mediaPath: string; alt: string }) {
  if (latest.status === "loading") return <LoadingState />
  if (latest.status === "none") return <p className="public__empty">{latest.text}</p>
  const { item } = latest
  return (
    <figure className="public__figure">
      {item.body && <p className="public__text">{item.body}</p>}
      {item.has_image && <img className="public__image" src={`${mediaPath}?v=${item.id}`} alt={alt} />}
      <figcaption className="public__caption">نُشر في {formatDateTime(item.published_at)}</figcaption>
    </figure>
  )
}

export function PublicPage() {
  const price = useLatest("/api/prices/latest/", NO_PRICES)
  const crossing = useLatest("/api/crossings/latest/", NO_CROSSINGS)
  const [webComplaints, setWebComplaints] = useState(true)
  useEffect(() => {
    apiRequest<{ web_complaints_enabled?: boolean }>("/api/settings/public/").then((result) => {
      if (result.ok && result.data && result.data.web_complaints_enabled === false) setWebComplaints(false)
    })
  }, [])

  return (
    <div className="portal" dir="rtl" lang="ar">
      <header className="portal__bar">
        <p className="portal__ministry">وزارة الاقتصاد الوطني</p>
        <nav className="portal__nav" aria-label="أقسام الصفحة">
          <a href="#complaint">تقديم شكوى</a>
          <a href="#prices">الأسعار</a>
          <a href="#crossings">المعابر</a>
        </nav>
      </header>
      <main>
        <section className="portal__hero">
          <p className="portal__kicker">خدمة عامة</p>
          <h1>حماية المستهلك</h1>
          <p className="portal__lead">
            قدّم شكواك مباشرة. نكتفي بمكان الواقعة وما حدث، من غير اسم ومن غير متابعة لاحقة.
          </p>
          <a className="portal__cta" href="#complaint">
            ابدأ الشكوى
          </a>
        </section>
        <ol className="portal__steps">
          <li>
            <strong>١</strong>
            <span>حدد المحافظة والمنطقة</span>
          </li>
          <li>
            <strong>٢</strong>
            <span>صف ما حدث بعنوان وتفاصيل</span>
          </li>
          <li>
            <strong>٣</strong>
            <span>نحوّلها للجهة المختصة</span>
          </li>
        </ol>
        <section className="portal__card" id="complaint" aria-labelledby="complaint-title">
          <h2 id="complaint-title">تقديم شكوى</h2>
          <p className="portal__note">الصورة اختيارية. بعد الإرسال تظهر جملة الاستلام فقط.</p>
          {webComplaints ? <ComplaintForm /> : <p className="public__empty">تقديم الشكاوى عبر الموقع متوقف حالياً.</p>}
        </section>
        <div className="portal__side">
          <section className="portal__card" id="prices" aria-labelledby="prices-title">
            <h2 id="prices-title">قائمة الأسعار</h2>
            <Bulletin latest={price} mediaPath="/api/media/prices/latest/" alt="قائمة الأسعار الحالية" />
          </section>
          <section className="portal__card" id="crossings" aria-labelledby="crossings-title">
            <h2 id="crossings-title">حركة المعابر</h2>
            <Bulletin latest={crossing} mediaPath="/api/media/crossings/latest/" alt="حركة المعابر الحالية" />
          </section>
        </div>
      </main>
    </div>
  )
}
