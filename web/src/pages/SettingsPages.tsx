import { useState, type FormEvent } from "react"
import { Button, TextField } from "../design-system"
import { apiRequest } from "../api"
import { failureText, NoticeLine, useLoad, type Notice } from "./common"
import { TelegramHealthPage } from "./TelegramHealthPage"

type Settings = {
  web_complaints_enabled: boolean
  telegram_bot_username: string
  telegram_bot_configured: boolean
  telegram_webhook_secret_configured: boolean
}

export function SystemSettingsPage() {
  const { state, reload } = useLoad(() => apiRequest<Settings>("/api/system-settings/"), [])
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)

  const save = async (enabled: boolean) => {
    setBusy(true)
    const result = await apiRequest<Settings>("/api/system-settings/", {
      method: "PATCH",
      body: { web_complaints_enabled: enabled },
    })
    setBusy(false)
    if (!result.ok) setNotice({ tone: "error", text: failureText(result) })
    else {
      setNotice({ tone: "ok", text: enabled ? "تقديم الشكاوى عبر الموقع مفعّل." : "تقديم الشكاوى عبر الموقع متوقف." })
      reload()
    }
  }

  const enabled = state.status === "ready" ? state.data.web_complaints_enabled : true
  return (
    <div className="page">
      <NoticeLine notice={notice} />
      <section className="sheet">
        <h2 className="account__heading">الشكاوى عبر الموقع</h2>
        <p className="account__note">عند الإيقاف تبقى صفحة الجمهور ظاهرة، ويرفض الموقع أي شكوى جديدة من الويب. تلغرام لا يتأثر.</p>
        <Button loading={busy} onClick={() => save(!enabled)}>
          {enabled ? "إيقاف الشكاوى عبر الموقع" : "تفعيل الشكاوى عبر الموقع"}
        </Button>
      </section>
    </div>
  )
}

export function TelegramSettingsPage() {
  const { state, reload } = useLoad(() => apiRequest<Settings>("/api/system-settings/"), [])
  const [username, setUsername] = useState("")
  const [token, setToken] = useState("")
  const [secret, setSecret] = useState("")
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)
  const current = state.status === "ready" ? state.data : null

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    const result = await apiRequest<Settings>("/api/system-settings/", {
      method: "PATCH",
      body: {
        telegram_bot_username: username || current?.telegram_bot_username,
        telegram_bot_token: token,
        telegram_webhook_secret: secret,
      },
    })
    setBusy(false)
    if (!result.ok) {
      setNotice({ tone: "error", text: failureText(result) })
      return
    }
    setToken("")
    setSecret("")
    setNotice({ tone: "ok", text: "حُفظت إعدادات تلغرام وأعيدت محاولة تسجيل الويب هوك." })
    reload()
  }

  return (
    <div className="page">
      <NoticeLine notice={notice} />
      <form className="sheet" onSubmit={onSubmit}>
        <h2 className="account__heading">ربط البوت</h2>
        <p className="account__note">
          اسم البوت الحالي: {current?.telegram_bot_username || "غير مضاف"}. الرمز{" "}
          {current?.telegram_bot_configured ? "محفوظ" : "غير محفوظ"}، وسر الويب هوك{" "}
          {current?.telegram_webhook_secret_configured ? "محفوظ" : "غير محفوظ"}. اترك الرمز فارغاً إذا أردت الإبقاء على
          المحفوظ. ربط الموظفين يبقى من صفحة المستخدمين.
        </p>
        <TextField label="اسم البوت" name="bot" value={username} placeholder={current?.telegram_bot_username} onChange={(e) => setUsername(e.target.value)} />
        <TextField label="رمز البوت" name="token" type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" />
        <TextField label="سر الويب هوك" name="secret" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} autoComplete="off" />
        <Button type="submit" loading={busy}>
          حفظ وإعادة التسجيل
        </Button>
      </form>
      <TelegramHealthPage />
    </div>
  )
}
