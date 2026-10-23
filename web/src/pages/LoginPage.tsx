import { useState, type FormEvent } from "react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"
import { Button, LoadingState, TextField } from "../design-system"
import { errorDetail, fetchMe, postLogin, readCookie } from "../api"
import { useAuth } from "../auth"
import { HOME_PATH } from "../routes"

export const INVALID_CREDENTIALS = "بيانات الدخول غير صحيحة."

export function LoginPage() {
  const { session, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? HOME_PATH

  if (session.status === "loading") {
    return (
      <div className="app-center" dir="rtl" lang="ar">
        <LoadingState />
      </div>
    )
  }
  if (session.status === "signed_in") return <Navigate to={from} replace />

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    if (!username.trim() || !password) {
      setError("أدخل اسم المستخدم وكلمة المرور.")
      return
    }
    setBusy(true)
    if (!readCookie("csrftoken")) await fetchMe()
    const result = await postLogin(username.trim(), password)
    setBusy(false)
    if (result.ok && result.data) {
      signIn(result.data)
      navigate(from, { replace: true })
      return
    }
    if (result.status === 400) setError(errorDetail(result.data) ?? INVALID_CREDENTIALS)
    else if (result.status === 0) setError("تعذّر الاتصال بالخادم. تحقق من الشبكة وأعد المحاولة.")
    else setError("تعذّر تسجيل الدخول الآن. أعد المحاولة لاحقاً.")
  }

  return (
    <div className="login" dir="rtl" lang="ar">
      <section className="login__panel" aria-labelledby="login-title">
        <p className="login__eyebrow">منظومة حماية المستهلك</p>
        <h1 className="login__title" id="login-title">
          تسجيل الدخول
        </h1>
        <p className="login__lede">ادخل ببيانات الحساب التي سلّمتها لك الإدارة.</p>
        <form className="login__form" onSubmit={onSubmit} noValidate>
          <TextField
            label="اسم المستخدم"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <TextField
            label="كلمة المرور"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <p className="app-alert" role="alert">
              {error}
            </p>
          )}
          <Button type="submit" loading={busy}>
            دخول
          </Button>
        </form>
      </section>
    </div>
  )
}
