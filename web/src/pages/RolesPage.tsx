import { useState, type FormEvent } from "react"
import { Button, DataTable, Dialog, TextField, type Column } from "../design-system"
import { apiRequest, type StaffRole } from "../api"
import { AreaTabs } from "./UsersPage"
import { Loaded, NoticeLine, failureText, useLoad, type Notice } from "./common"

export const ROLE_PERMISSIONS = [
  { key: "can_view_all_complaints", label: "رؤية كل الشكاوى" },
  { key: "can_view_reports", label: "التقارير" },
  { key: "can_manage_users", label: "المستخدمون" },
  { key: "can_manage_geography", label: "المحافظات والمناطق" },
  { key: "can_publish", label: "الأسعار والمعابر" },
  { key: "can_view_field_missions", label: "رؤية المهام" },
  { key: "can_open_field_missions", label: "إنشاء مهام" },
  { key: "can_manage_settings", label: "إعدادات النظام وتلغرام" },
  { key: "can_impersonate", label: "الدخول بحساب مستخدم" },
  { key: "can_login_web", label: "الدخول من الموقع" },
] as const

type PermissionKey = (typeof ROLE_PERMISSIONS)[number]["key"]

const KIND_NAMES: Record<StaffRole["kind"], string> = {
  governor: "مدير المحافظة",
  inspector: "مفتش",
  legal: "الشؤون القانونية",
  custom: "دور مخصص",
}

type Draft = { name: string } & Record<PermissionKey, boolean>

function draftFrom(role?: StaffRole): Draft {
  return {
    name: role?.name ?? "",
    can_view_all_complaints: role?.can_view_all_complaints ?? false,
    can_view_reports: role?.can_view_reports ?? false,
    can_manage_users: role?.can_manage_users ?? false,
    can_manage_geography: role?.can_manage_geography ?? false,
    can_publish: role?.can_publish ?? false,
    can_view_field_missions: role?.can_view_field_missions ?? false,
    can_open_field_missions: role?.can_open_field_missions ?? false,
    can_manage_settings: role?.can_manage_settings ?? false,
    can_impersonate: role?.can_impersonate ?? false,
    can_login_web: role?.can_login_web ?? true,
  }
}

function bodyOf(draft: Draft) {
  return {
    name: draft.name.trim(),
    can_view_all_complaints: draft.can_view_all_complaints,
    can_view_reports: draft.can_view_reports,
    can_manage_users: draft.can_manage_users,
    can_manage_geography: draft.can_manage_geography,
    can_publish: draft.can_publish,
    can_view_field_missions: draft.can_view_field_missions,
    can_open_field_missions: draft.can_open_field_missions,
    can_manage_settings: draft.can_manage_settings,
    can_impersonate: draft.can_impersonate,
    can_login_web: draft.can_login_web,
  }
}

function RoleForm({
  role,
  onSaved,
  onCancel,
}: {
  role?: StaffRole
  onSaved: (notice: Notice) => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState<Draft>(() => draftFrom(role))
  const [nameError, setNameError] = useState("")
  const [notice, setNotice] = useState<Notice>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!draft.name.trim()) {
      setNameError("اسم الدور مطلوب.")
      return
    }
    setNameError("")
    setBusy(true)
    const result = role
      ? await apiRequest<StaffRole>(`/api/roles/${role.id}/`, { method: "PATCH", body: bodyOf(draft) })
      : await apiRequest<StaffRole>("/api/roles/", { method: "POST", body: bodyOf(draft) })
    setBusy(false)
    if (result.ok) onSaved({ tone: "ok", text: role ? "تم حفظ الدور." : "تم إنشاء الدور." })
    else setNotice({ tone: "error", text: failureText(result) })
  }

  return (
    <form className="sheet__form" onSubmit={onSubmit} noValidate>
      <TextField
        label="اسم الدور"
        name="name"
        value={draft.name}
        onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
        error={nameError}
        required
      />
      {role?.built_in && <p className="sheet__note">هذا دور أساسي. المسمى والصلاحيات يتغيران، ومسار العمل يبقى كما هو.</p>}
      <fieldset className="role-perms">
        <legend>الصلاحيات</legend>
        {ROLE_PERMISSIONS.map((item) => (
          <label key={item.key}>
            <input
              type="checkbox"
              name={item.key}
              checked={draft[item.key]}
              onChange={(e) => setDraft((d) => ({ ...d, [item.key]: e.target.checked }))}
            />
            <span>{item.label}</span>
          </label>
        ))}
      </fieldset>
      <NoticeLine notice={notice} />
      <div className="sheet__actions">
        <Button type="submit" loading={busy}>
          {role ? "حفظ الدور" : "إنشاء الدور"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  )
}

function DeleteRole({ role, onDone, onCancel }: { role: StaffRole; onDone: (notice: Notice) => void; onCancel: () => void }) {
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  const onConfirm = async () => {
    setBusy(true)
    const result = await apiRequest(`/api/roles/${role.id}/`, { method: "DELETE" })
    setBusy(false)
    if (result.ok) onDone({ tone: "ok", text: "تم حذف الدور." })
    else setNotice({ tone: "error", text: failureText(result) })
  }
  return (
    <div className="confirm" role="alertdialog" aria-modal="false" aria-labelledby="role-delete-title">
      <p className="confirm__title" id="role-delete-title">
        حذف الدور {role.name}؟
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

export function RolesPage() {
  const [panel, setPanel] = useState<"create" | StaffRole | "delete" | null>(null)
  const [target, setTarget] = useState<StaffRole | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const { state, reload } = useLoad(() => apiRequest<{ results: StaffRole[] }>("/api/roles/"), [])
  const finish = (next: Notice) => {
    setPanel(null)
    setTarget(null)
    setNotice(next)
    reload()
  }
  const editing = typeof panel === "object" ? panel : null
  const columns: Column<StaffRole>[] = [
    { key: "name", header: "الدور", render: (row) => row.name },
    { key: "kind", header: "النوع", render: (row) => (row.built_in ? KIND_NAMES[row.kind] : "دور مخصص") },
    {
      key: "permissions",
      header: "الصلاحيات",
      render: (row) => ROLE_PERMISSIONS.filter((item) => row[item.key]).map((item) => item.label).join("، ") || "—",
    },
  ]

  return (
    <div className="page">
      <AreaTabs current="roles" />
      <div className="page__bar">
        <Button onClick={() => setPanel("create")}>دور جديد</Button>
      </div>
      {panel === "create" && (
        <Dialog title="دور جديد" onClose={() => setPanel(null)}>
          <RoleForm onSaved={finish} onCancel={() => setPanel(null)} />
        </Dialog>
      )}
      {editing && (
        <Dialog title={`تعديل ${editing.name}`} onClose={() => setPanel(null)}>
          <RoleForm key={editing.id} role={editing} onSaved={finish} onCancel={() => setPanel(null)} />
        </Dialog>
      )}
      {panel === "delete" && target && (
        <Dialog title="حذف الدور" onClose={() => setPanel(null)}>
          <DeleteRole role={target} onDone={finish} onCancel={() => setPanel(null)} />
        </Dialog>
      )}
      <NoticeLine notice={notice} />
      <Loaded state={state} onRetry={reload}>
        {(data) => (
          <DataTable
            caption="الأدوار"
            columns={columns}
            rows={data.results}
            getRowId={(row) => row.id}
            getRowLabel={(row) => row.name}
            emptyTitle="لا توجد أدوار."
            rowActions={(row) => [
              { id: "edit", label: "تعديل", onSelect: () => setPanel(row) },
              ...(!row.built_in
                ? [{ id: "delete", label: "حذف", tone: "danger" as const, onSelect: () => { setTarget(row); setPanel("delete") } }]
                : []),
            ]}
          />
        )}
      </Loaded>
    </div>
  )
}
