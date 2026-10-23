import { useState, type FormEvent } from "react"
import { Button, TextField } from "../design-system"
import { errorDetail, patchDisplayName, postPasswordChange } from "../api"
import { useAuth } from "../auth"

export const PASSWORD_MIN_LENGTH = 12

type Notice = { tone: "ok" | "error"; text: string } | null

function NoticeLine({ notice }: { notice: Notice }) {
  if (!notice) return null
  return (
    <p className={notice.tone === "ok" ? "app-notice" : "app-alert"} role={notice.tone === "ok" ? "status" : "alert"}>
      {notice.text}
    </p>
  )
}

function DisplayNameForm() {
  const { session, updateUser } = useAuth()
  const user = session.status === "signed_in" ? session.user : null
  const [displayName, setDisplayName] = useState(user?.display_name ?? "")
  const [error, setError] = useState<string | undefined>()
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)
  if (!user) return null

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice(null)
    const value = displayName.trim()
    if (!value) {
      setError("أدخل الاسم الظاهر.")
      return
    }
    setError(undefined)
    setBusy(true)
    const result = await patchDisplayName(user.id, value)
    setBusy(false)
    if (result.ok) {
      updateUser({ display_name: result.data?.display_name ?? value })
      setNotice({ tone: "ok", text: "تم حفظ الاسم الظاهر." })
    } else {
      setNotice({ tone: "error", text: errorDetail(result.data) ?? "تعذّر حفظ الاسم الظاهر. أعد المحاولة." })
    }
  }

  return (
    <section className="account__section" aria-labelledby="account-name">
      <h2 className="account__heading" id="account-name">
        الاسم الظاهر
      </h2>
      <p className="account__note">يظهر هذا الاسم في سجل المتابعة وفي رأس الصفحة.</p>
      <form className="account__form" onSubmit={onSubmit} noValidate>
        <TextField
          label="الاسم الظاهر"
          name="display_name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          error={error}
          required
        />
        <NoticeLine notice={notice} />
        <div className="account__actions">
          <Button type="submit" loading={busy}>
            حفظ الاسم
          </Button>
        </div>
      </form>
    </section>
  )
}

type PasswordErrors = { current?: string; next?: string; confirm?: string }

function PasswordForm() {
  const { session } = useAuth()
  const user = session.status === "signed_in" ? session.user : null
  const [current, setCurrent] = useState("")
  const [next, setNext] = useState("")
  const [confirm, setConfirm] = useState("")
  const [errors, setErrors] = useState<PasswordErrors>({})
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)
  if (!user) return null

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice(null)
    const found: PasswordErrors = {}
    if (!current) found.current = "أدخل كلمة المرور الحالية."
    if (next.length < PASSWORD_MIN_LENGTH) found.next = `يجب ألا تقل كلمة المرور الجديدة عن ${PASSWORD_MIN_LENGTH} حرفاً.`
    if (!confirm) found.confirm = "أعد كتابة كلمة المرور الجديدة."
    else if (confirm !== next) found.confirm = "تأكيد كلمة المرور لا يطابق الكلمة الجديدة."
    setErrors(found)
    if (Object.keys(found).length) return

    setBusy(true)
    const result = await postPasswordChange(user.id, {
      password: next,
      password_confirm: confirm,
      current_password: current,
    })
    setBusy(false)
    if (result.ok) {
      setCurrent("")
      setNext("")
      setConfirm("")
      setNotice({ tone: "ok", text: "تم تغيير كلمة المرور." })
      return
    }
    let text: string
    if (result.status === 404 || result.status === 405) text = "تغيير كلمة المرور غير متاح على الخادم حالياً. لم تتغير كلمة المرور."
    else if (result.status === 0) text = "تعذّر الاتصال بالخادم. لم تتغير كلمة المرور."
    else text = errorDetail(result.data) ?? "رفض الخادم تغيير كلمة المرور. لم تتغير كلمة المرور."
    setNotice({ tone: "error", text })
  }

  return (
    <section className="account__section" aria-labelledby="account-password">
      <h2 className="account__heading" id="account-password">
        كلمة المرور
      </h2>
      <p className="account__note">اختر كلمة مرور من {PASSWORD_MIN_LENGTH} حرفاً على الأقل.</p>
      <form className="account__form" onSubmit={onSubmit} noValidate>
        <TextField
          label="كلمة المرور الحالية"
          name="current_password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          error={errors.current}
          required
        />
        <TextField
          label="كلمة المرور الجديدة"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={PASSWORD_MIN_LENGTH}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          error={errors.next}
          required
        />
        <TextField
          label="تأكيد كلمة المرور الجديدة"
          name="password_confirm"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          error={errors.confirm}
          required
        />
        <NoticeLine notice={notice} />
        <div className="account__actions">
          <Button type="submit" loading={busy}>
            تغيير كلمة المرور
          </Button>
        </div>
      </form>
    </section>
  )
}

export function AccountPage() {
  return (
    <div className="account">
      <DisplayNameForm />
      <PasswordForm />
    </div>
  )
}
