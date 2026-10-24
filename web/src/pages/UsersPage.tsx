import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import {
  Button,
  DataTable,
  Dialog,
  FilterBar,
  Select,
  TextField,
  type BulkAction,
  type Column,
  type FilterField,
  type FilterValues,
} from "../design-system"
import { apiRequest, withQuery, type ActionResult, type Page, type Role, type SessionUser, type UserRow } from "../api"
import { useAuthOptional } from "../auth"
import { HOME_PATH } from "../routes"
import { PASSWORD_MIN_LENGTH } from "./AccountPage"
import { Loaded, NoticeLine, PAGE_SIZE, Section, actionNotice, failureText, useLoad, type Notice } from "./common"
import { nameOf, optionsOf, useAdminGeography, type Geography } from "./geo"

export const ROLE_NAMES: Record<Role, string> = {
  admin: "مدير النظام",
  governor: "مدير المحافظة",
  inspector: "مفتش",
  legal: "الشؤون القانونية",
}

const ROLE_OPTIONS = (Object.keys(ROLE_NAMES) as Role[]).map((role) => ({ value: role, label: ROLE_NAMES[role] }))

const FLAGS = [
  { key: "can_publish_prices", label: "نشر قائمة الأسعار" },
  { key: "can_publish_crossings", label: "نشر حركة المعابر" },
  { key: "can_view_all_complaints", label: "رؤية كل الشكاوى" },
  { key: "can_login_web", label: "الدخول من الموقع" },
  { key: "can_open_field_missions", label: "فتح مهمة ميدانية" },
  { key: "can_view_field_missions", label: "رؤية المهمات الميدانية" },
] as const

type FlagKey = (typeof FLAGS)[number]["key"]

const YES_NO = [
  { value: "0", label: "غير ممنوحة" },
  { value: "1", label: "ممنوحة" },
]

const SCHEMA: FilterField[] = [
  { type: "search", key: "q", label: "بحث", placeholder: "اسم المستخدم أو الاسم الظاهر" },
  { type: "select", key: "role", label: "الدور", options: ROLE_OPTIONS },
  {
    type: "select",
    key: "is_active",
    label: "الحالة",
    options: [
      { value: "1", label: "مفعّل" },
      { value: "0", label: "معطّل" },
    ],
  },
]

const rowId = (row: UserRow) => row.id

type Panel =
  | { kind: "create" }
  | { kind: "edit"; user: UserRow }
  | { kind: "password"; user: UserRow }
  | { kind: "telegram"; user: UserRow }
  | { kind: "delete"; user: UserRow }
  | { kind: "enter"; user: UserRow }
  | null

type Draft = {
  username: string
  display_name: string
  password: string
  role: Role | ""
  governorate: string
  region: string
} & Record<FlagKey, boolean>

function draftFrom(user?: UserRow): Draft {
  return {
    username: user?.username ?? "",
    display_name: user?.display_name ?? "",
    password: "",
    role: user?.role ?? "",
    governorate: user?.governorate ? String(user.governorate) : "",
    region: user?.region ? String(user.region) : "",
    can_publish_prices: user?.can_publish_prices ?? false,
    can_publish_crossings: user?.can_publish_crossings ?? false,
    can_view_all_complaints: user?.can_view_all_complaints ?? false,
    can_login_web: user?.can_login_web ?? true,
    can_open_field_missions: user?.can_open_field_missions ?? false,
    can_view_field_missions: user?.can_view_field_missions ?? false,
  }
}

function UserForm({
  user,
  geo,
  onSaved,
  onCancel,
}: {
  user?: UserRow
  geo: Geography
  onSaved: (notice: Notice) => void
  onCancel: () => void
}) {
  const creating = !user
  const [draft, setDraft] = useState<Draft>(() => draftFrom(user))
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>({})
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }))

  const needsGovernorate = draft.role === "governor" || draft.role === "inspector"
  const needsRegion = draft.role === "inspector"
  const regionOptions = optionsOf(geo.regions.filter((r) => String(r.governorate) === draft.governorate))

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice(null)
    const found: typeof errors = {}
    if (creating && !draft.username.trim()) found.username = "أدخل اسم المستخدم."
    if (creating && draft.password.length < PASSWORD_MIN_LENGTH)
      found.password = `يجب ألا تقل كلمة المرور عن ${PASSWORD_MIN_LENGTH} حرفاً.`
    if (!draft.role) found.role = "اختر الدور."
    if (needsGovernorate && !draft.governorate) found.governorate = "اختر المحافظة."
    if (needsRegion && !draft.region) found.region = "اختر المنطقة."
    setErrors(found)
    if (Object.keys(found).length) return

    const body: Record<string, unknown> = {
      display_name: draft.display_name.trim(),
      role: draft.role,
      governorate: needsGovernorate ? Number(draft.governorate) : null,
      region: needsRegion ? Number(draft.region) : null,
      can_publish_prices: draft.can_publish_prices,
      can_publish_crossings: draft.can_publish_crossings,
      can_view_all_complaints: draft.can_view_all_complaints,
      can_login_web: draft.can_login_web,
      can_open_field_missions: draft.can_open_field_missions,
      can_view_field_missions: draft.can_view_field_missions,
    }
    if (creating) {
      body.username = draft.username.trim()
      body.password = draft.password
    }
    setBusy(true)
    const result = creating
      ? await apiRequest<UserRow>("/api/users/", { method: "POST", body })
      : await apiRequest<UserRow>(`/api/users/${user.id}/`, { method: "PATCH", body })
    setBusy(false)
    if (result.ok) onSaved({ tone: "ok", text: creating ? `تم إنشاء الحساب ${draft.username.trim()}.` : "تم حفظ التعديلات." })
    else setNotice({ tone: "error", text: failureText(result) })
  }

  return (
    <Section
      title={creating ? "مستخدم جديد" : `تعديل ${user.username}`}
      note={creating ? "سلّم كلمة المرور الأولى للموظف. يستطيع تغييرها من إعداداته." : "اسم المستخدم ثابت ولا يتغير."}
    >
      <form className="sheet__form" onSubmit={onSubmit} noValidate>
        <div className="sheet__grid">
          {creating && (
            <TextField
              label="اسم المستخدم"
              name="username"
              autoComplete="off"
              value={draft.username}
              onChange={(e) => set("username", e.target.value)}
              error={errors.username}
              required
            />
          )}
          <TextField
            label="الاسم الظاهر"
            name="display_name"
            value={draft.display_name}
            onChange={(e) => set("display_name", e.target.value)}
          />
          {creating && (
            <TextField
              label="كلمة المرور"
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={PASSWORD_MIN_LENGTH}
              value={draft.password}
              onChange={(e) => set("password", e.target.value)}
              error={errors.password}
              hint={`${PASSWORD_MIN_LENGTH} حرفاً على الأقل.`}
              required
            />
          )}
          <Select
            label="الدور"
            name="role"
            placeholder="اختر الدور"
            options={ROLE_OPTIONS}
            value={draft.role}
            onChange={(e) => set("role", e.target.value as Role)}
            error={errors.role}
            required
          />
          {needsGovernorate && (
            <Select
              label="المحافظة"
              name="governorate"
              placeholder="اختر المحافظة"
              options={optionsOf(geo.governorates)}
              value={draft.governorate}
              onChange={(e) => setDraft((d) => ({ ...d, governorate: e.target.value, region: "" }))}
              error={errors.governorate}
              required
            />
          )}
          {needsRegion && (
            <Select
              label="المنطقة"
              name="region"
              placeholder={draft.governorate ? "اختر المنطقة" : "اختر المحافظة أولاً"}
              options={regionOptions}
              value={draft.region}
              disabled={!draft.governorate}
              onChange={(e) => set("region", e.target.value)}
              error={errors.region}
              required
            />
          )}
          {FLAGS.map((flag) => (
            <Select
              key={flag.key}
              label={flag.label}
              name={flag.key}
              options={YES_NO}
              value={draft[flag.key] ? "1" : "0"}
              onChange={(e) => set(flag.key, e.target.value === "1")}
            />
          ))}
        </div>
        <NoticeLine notice={notice} />
        <div className="sheet__actions">
          <Button type="submit" loading={busy}>
            {creating ? "إنشاء الحساب" : "حفظ التعديلات"}
          </Button>
          <Button variant="ghost" onClick={onCancel}>
            إلغاء
          </Button>
        </div>
      </form>
    </Section>
  )
}

function PasswordPanel({ user, onClose }: { user: UserRow; onClose: () => void }) {
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({})
  const [notice, setNotice] = useState<Notice>(null)
  const [revealed, setRevealed] = useState<string | null>(null)
  const [busy, setBusy] = useState<"set" | "reset" | null>(null)

  const onSet = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setNotice(null)
    setRevealed(null)
    const found: typeof errors = {}
    if (password.length < PASSWORD_MIN_LENGTH) found.password = `يجب ألا تقل كلمة المرور عن ${PASSWORD_MIN_LENGTH} حرفاً.`
    if (confirm !== password) found.confirm = "التأكيد لا يطابق كلمة المرور."
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy("set")
    const result = await apiRequest(`/api/users/${user.id}/password/`, {
      method: "POST",
      body: { mode: "set", password, password_confirm: confirm },
    })
    setBusy(null)
    if (result.ok) {
      setPassword("")
      setConfirm("")
      setNotice({ tone: "ok", text: "تم تغيير كلمة المرور وأُلغيت جلسات المستخدم." })
    } else {
      setNotice({ tone: "error", text: failureText(result) })
    }
  }

  const onReset = async () => {
    setNotice(null)
    setRevealed(null)
    setBusy("reset")
    const result = await apiRequest<{ password: string }>(`/api/users/${user.id}/password/`, {
      method: "POST",
      body: { mode: "reset" },
    })
    setBusy(null)
    if (result.ok && result.data?.password) setRevealed(result.data.password)
    else setNotice({ tone: "error", text: failureText(result) })
  }

  return (
    <Section title={`كلمة مرور ${user.username}`} note="أي تغيير يُلغي جلسات هذا المستخدم.">
      <form className="sheet__form" onSubmit={onSet} noValidate>
        <div className="sheet__grid">
          <TextField
            label="كلمة المرور الجديدة"
            name="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
            required
          />
          <TextField
            label="تأكيد كلمة المرور"
            name="password_confirm"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            error={errors.confirm}
            required
          />
        </div>
        <div className="sheet__actions">
          <Button type="submit" loading={busy === "set"}>
            تعيين كلمة المرور
          </Button>
          <Button variant="secondary" loading={busy === "reset"} onClick={onReset}>
            إعادة تعيين كلمة المرور
          </Button>
          <Button variant="ghost" onClick={onClose}>
            إغلاق
          </Button>
        </div>
      </form>
      <NoticeLine notice={notice} />
      {revealed && (
        <div className="secret" role="status">
          <p className="secret__label">كلمة المرور الجديدة. تظهر هذه المرة فقط، انقلها إلى الموظف الآن.</p>
          <output className="secret__value" dir="ltr" data-testid="revealed-password">
            {revealed}
          </output>
          <Button variant="ghost" size="sm" onClick={() => setRevealed(null)}>
            تم النقل، أخفِ الكلمة
          </Button>
        </div>
      )}
    </Section>
  )
}

function TelegramPanel({ user, onClose }: { user: UserRow; onClose: () => void }) {
  const [link, setLink] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState<"link" | "unlink" | null>(null)

  const onLink = async () => {
    setNotice(null)
    setLink(null)
    setBusy("link")
    const result = await apiRequest<{ link: string }>(`/api/users/${user.id}/telegram-link/`, { method: "POST" })
    setBusy(null)
    if (result.ok && result.data?.link) setLink(result.data.link)
    else setNotice({ tone: "error", text: failureText(result) })
  }

  const onUnlink = async () => {
    setNotice(null)
    setLink(null)
    setBusy("unlink")
    const result = await apiRequest(`/api/users/${user.id}/telegram-link/`, { method: "DELETE" })
    setBusy(null)
    if (result.ok) setNotice({ tone: "ok", text: "تم فك ربط تلغرام." })
    else setNotice({ tone: "error", text: failureText(result) })
  }

  return (
    <Section title={`تلغرام ${user.username}`} note="الرابط يظهر مرة واحدة، ويصلح ٢٤ ساعة لاستخدام واحد.">
      <div className="sheet__actions">
        <Button loading={busy === "link"} onClick={onLink}>
          إنشاء رابط الربط
        </Button>
        <Button variant="secondary" loading={busy === "unlink"} onClick={onUnlink}>
          فك الربط
        </Button>
        <Button variant="ghost" onClick={onClose}>
          إغلاق
        </Button>
      </div>
      <NoticeLine notice={notice} />
      {link && (
        <div className="secret" role="status">
          <p className="secret__label">انقل هذا الرابط إلى الموظف الآن. لن يُعرض مرة أخرى.</p>
          <output className="secret__value" dir="ltr">
            {link}
          </output>
        </div>
      )}
    </Section>
  )
}

function DeletePanel({ user, onDone, onCancel }: { user: UserRow; onDone: (notice: Notice) => void; onCancel: () => void }) {
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  const onConfirm = async () => {
    setBusy(true)
    const result = await apiRequest(`/api/users/${user.id}/`, { method: "DELETE" })
    setBusy(false)
    if (result.ok) onDone({ tone: "ok", text: `تم حذف الحساب ${user.username}.` })
    else setNotice({ tone: "error", text: failureText(result) })
  }
  return (
    <div className="confirm" role="alertdialog" aria-modal="false" aria-labelledby="confirm-title" aria-describedby="confirm-desc">
      <p className="confirm__title" id="confirm-title">
        حذف الحساب {user.username}؟
      </p>
      <p className="confirm__desc" id="confirm-desc">
        يسقط الدخول والجلسات وربط تلغرام. سطور المتابعة تبقى بالاسم المنسوخ. لا يمكن التراجع.
      </p>
      <NoticeLine notice={notice} />
      <div className="sheet__actions">
        <Button variant="danger" loading={busy} onClick={onConfirm}>
          تأكيد الحذف
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </div>
  )
}

function EnterPanel({
  user,
  onEntered,
  onCancel,
}: {
  user: UserRow
  onEntered: (session: SessionUser) => void
  onCancel: () => void
}) {
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)
  const name = user.display_name || user.username
  const onConfirm = async () => {
    setBusy(true)
    const result = await apiRequest<SessionUser>(`/api/users/${user.id}/enter/`, { method: "POST" })
    setBusy(false)
    if (result.ok && result.data) onEntered(result.data)
    else setNotice({ tone: "error", text: failureText(result) })
  }
  return (
    <div className="confirm" role="alertdialog" aria-modal="false" aria-labelledby="enter-title" aria-describedby="enter-desc">
      <p className="confirm__title" id="enter-title">
        الدخول بحساب {name}؟
      </p>
      <p className="confirm__desc" id="enter-desc">
        سترى الموقع كما يراه هذا الحساب. تعود إلى حسابك من الشريط أعلى الصفحة.
      </p>
      <NoticeLine notice={notice} />
      <div className="sheet__actions">
        <Button loading={busy} onClick={onConfirm}>
          دخول بالحساب
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </div>
  )
}

export function UsersPage() {
  const navigate = useNavigate()
  const auth = useAuthOptional()
  const selfId = auth?.session.status === "signed_in" ? auth.session.user.id : null
  const [filters, setFilters] = useState<FilterValues>({})
  const [page, setPage] = useState(1)
  const [panel, setPanel] = useState<Panel>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const geo = useAdminGeography()

  const { state, reload } = useLoad(
    () =>
      apiRequest<Page<UserRow>>(
        withQuery("/api/users/", { q: filters.q, role: filters.role, is_active: filters.is_active, page, page_size: PAGE_SIZE }),
      ),
    [filters.q, filters.role, filters.is_active, page],
  )

  const finish = (next: Notice) => {
    setPanel(null)
    setNotice(next)
    reload()
  }

  const runBulk = async (action: "activate" | "deactivate", ids: number[]) => {
    setNotice(null)
    const result = await apiRequest<ActionResult>("/api/users/actions/", { method: "POST", body: { action, ids } })
    setNotice(actionNotice(result, action === "activate" ? "تم تفعيل الحسابات المحددة." : "تم تعطيل الحسابات المحددة."))
    reload()
  }

  const bulkActions: BulkAction[] = [
    { id: "activate", label: "تفعيل", onRun: (ids) => runBulk("activate", ids.map(Number)) },
    { id: "deactivate", label: "تعطيل", tone: "danger", onRun: (ids) => runBulk("deactivate", ids.map(Number)) },
  ]

  const columns: Column<UserRow>[] = [
    { key: "username", header: "اسم المستخدم", render: (row) => <span dir="ltr">{row.username}</span> },
    { key: "display_name", header: "الاسم الظاهر", render: (row) => row.display_name || "—" },
    { key: "role", header: "الدور", render: (row) => ROLE_NAMES[row.role] ?? row.role },
    { key: "governorate", header: "المحافظة", render: (row) => nameOf(geo.governorates, row.governorate) },
    { key: "region", header: "المنطقة", render: (row) => nameOf(geo.regions, row.region) },
    {
      key: "flags",
      header: "صلاحيات إضافية",
      render: (row) => FLAGS.filter((f) => row[f.key]).map((f) => f.label).join("، ") || "—",
    },
    {
      key: "is_active",
      header: "الحالة",
      render: (row) => (row.is_active ? "مفعّل" : <span className="app-muted">معطّل</span>),
    },
  ]

  return (
    <div className="page">
      <div className="page__bar">
        <Button onClick={() => setPanel({ kind: "create" })} disabled={panel?.kind === "create"}>
          إضافة مستخدم
        </Button>
      </div>
      {panel?.kind === "create" && (
        <Dialog title="مستخدم جديد" onClose={() => setPanel(null)}>
          <UserForm geo={geo} onSaved={finish} onCancel={() => setPanel(null)} />
        </Dialog>
      )}
      {panel?.kind === "edit" && (
        <Dialog title={`تعديل ${panel.user.username}`} onClose={() => setPanel(null)}>
          <UserForm key={panel.user.id} user={panel.user} geo={geo} onSaved={finish} onCancel={() => setPanel(null)} />
        </Dialog>
      )}
      {panel?.kind === "password" && (
        <Dialog title="كلمة المرور" onClose={() => setPanel(null)}>
          <PasswordPanel key={panel.user.id} user={panel.user} onClose={() => setPanel(null)} />
        </Dialog>
      )}
      {panel?.kind === "telegram" && (
        <Dialog title="ربط تلغرام" onClose={() => setPanel(null)}>
          <TelegramPanel key={panel.user.id} user={panel.user} onClose={() => setPanel(null)} />
        </Dialog>
      )}
      {panel?.kind === "delete" && (
        <Dialog title="حذف الحساب" onClose={() => setPanel(null)}>
          <DeletePanel key={panel.user.id} user={panel.user} onDone={finish} onCancel={() => setPanel(null)} />
        </Dialog>
      )}
      {panel?.kind === "enter" && (
        <Dialog title="دخول بالحساب" onClose={() => setPanel(null)}>
          <EnterPanel
            key={panel.user.id}
            user={panel.user}
            onCancel={() => setPanel(null)}
            onEntered={(session) => {
              auth?.signIn(session)
              navigate(HOME_PATH)
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
            caption="المستخدمون"
            columns={columns}
            rows={data.results}
            getRowId={rowId}
            getRowLabel={(row) => row.username}
            bulkActions={bulkActions}
            emptyTitle="لا يوجد مستخدمون مطابقون."
            rowActions={(row) => [
              ...(row.is_active && row.id !== selfId
                ? [{ id: "enter", label: "دخول بالحساب", onSelect: () => setPanel({ kind: "enter", user: row }) }]
                : []),
              { id: "edit", label: "تعديل", onSelect: () => setPanel({ kind: "edit", user: row }) },
              { id: "password", label: "كلمة المرور", onSelect: () => setPanel({ kind: "password", user: row }) },
              { id: "telegram", label: "تلغرام", onSelect: () => setPanel({ kind: "telegram", user: row }) },
              { id: "delete", label: "حذف", tone: "danger", onSelect: () => setPanel({ kind: "delete", user: row }) },
            ]}
            pagination={{ page: data.page, pageSize: data.page_size, total: data.count, onPageChange: setPage }}
          />
        )}
      </Loaded>
    </div>
  )
}
