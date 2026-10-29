import { useState, type FormEvent } from "react"
import { Button, DataTable, Dialog, Select, TextField, type Column } from "../design-system"
import { apiRequest } from "../api"
import { Loaded, NoticeLine, failureText, useLoad, type Notice } from "./common"

type Choice = { id: string; label: string }
type BotButton = {
  id: number
  label: string
  target: string
  target_label: string
  audience: string
  audience_label: string
  row: number
  position: number
  enabled: boolean
  style: string
  style_label: string
}
type ButtonList = { results: BotButton[]; actions: Choice[]; audiences: Choice[] }

const empty = { label: "", target: "nw", audience: "everyone", row: "1", position: "1", enabled: "1", style: "" }

export function BotButtonsPage() {
  const { state, reload } = useLoad(() => apiRequest<ButtonList>("/api/telegram/buttons/"), [])
  const [notice, setNotice] = useState<Notice>(null)
  const [editing, setEditing] = useState<BotButton | "new" | null>(null)
  const [removing, setRemoving] = useState<BotButton | null>(null)

  const finish = (next: Notice) => {
    setEditing(null)
    setRemoving(null)
    setNotice(next)
    reload()
  }

  const columns: Column<BotButton>[] = [
    { key: "label", header: "الزر في التلجرام", render: (row) => row.label },
    { key: "target", header: "الضغطة تفتح", render: (row) => row.target_label },
    { key: "audience", header: "من يراه", render: (row) => row.audience_label },
    { key: "place", header: "الصف", render: (row) => `${row.row}.${row.position}` },
    { key: "style", header: "اللون", render: (row) => row.style_label || "بلا لون" },
    { key: "enabled", header: "الظهور", render: (row) => (row.enabled ? "ظاهر" : "مخفي") },
  ]

  return (
    <div className="page">
      <section className="sheet">
        <h2 className="account__heading">أزرار البوت</h2>
        <p className="account__note">
          كل زر ظاهر في تلغرام يوجّه ضغطته إلى زر موجود. تغيير الاسم أو التوجيه يظهر بعد أن يفتح الموظف القائمة من جديد.
          الوجهة تبقى خاضعة لصلاحية الشخص.
        </p>
        <Button onClick={() => setEditing("new")}>زر جديد</Button>
      </section>
      <NoticeLine notice={notice} />
      {editing && state.status === "ready" && (
        <Dialog title={editing === "new" ? "زر جديد" : `تعديل ${editing.label}`} onClose={() => setEditing(null)}>
          <ButtonForm
            button={editing === "new" ? null : editing}
            actions={state.data.actions}
            audiences={state.data.audiences}
            onSaved={finish}
            onCancel={() => setEditing(null)}
          />
        </Dialog>
      )}
      {removing && (
        <Dialog title="حذف الزر" onClose={() => setRemoving(null)}>
          <RemoveButton button={removing} onDone={finish} onCancel={() => setRemoving(null)} />
        </Dialog>
      )}
      <Loaded state={state} onRetry={reload}>
        {(data) => (
          <DataTable
            caption="أزرار البوت"
            actionMenu
            columns={columns}
            rows={data.results}
            getRowId={(row) => row.id}
            getRowLabel={(row) => row.label}
            emptyTitle="لا توجد أزرار."
            rowActions={(row) => [
              { id: "edit", label: "تعديل", onSelect: () => setEditing(row) },
              { id: "delete", label: "حذف", tone: "danger", onSelect: () => setRemoving(row) },
            ]}
          />
        )}
      </Loaded>
    </div>
  )
}

function ButtonForm({
  button,
  actions,
  audiences,
  onSaved,
  onCancel,
}: {
  button: BotButton | null
  actions: Choice[]
  audiences: Choice[]
  onSaved: (notice: Notice) => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState({
    label: button?.label ?? empty.label,
    target: button?.target ?? empty.target,
    audience: button?.audience ?? empty.audience,
    row: String(button?.row ?? empty.row),
    position: String(button?.position ?? empty.position),
    enabled: button ? (button.enabled ? "1" : "0") : empty.enabled,
    style: button?.style ?? empty.style,
  })
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  const set = (key: keyof typeof draft, value: string) => setDraft((current) => ({ ...current, [key]: value }))

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    const body = {
      label: draft.label.trim(),
      target: draft.target,
      audience: draft.audience,
      row: Number(draft.row),
      position: Number(draft.position),
      enabled: draft.enabled === "1",
      style: draft.style,
    }
    const result = await apiRequest<BotButton>(button ? `/api/telegram/buttons/${button.id}/` : "/api/telegram/buttons/", {
      method: button ? "PATCH" : "POST",
      body,
    })
    setBusy(false)
    if (!result.ok) {
      setNotice({ tone: "error", text: failureText(result) })
      return
    }
    onSaved({ tone: "ok", text: button ? "تم تعديل الزر." : "تمت إضافة الزر." })
  }

  return (
    <form className="sheet" onSubmit={onSubmit}>
      <TextField label="الاسم في التلجرام" name="label" value={draft.label} required onChange={(event) => set("label", event.target.value)} />
      <Select
        label="الضغطة تفتح"
        name="target"
        value={draft.target}
        options={actions.map((item) => ({ value: item.id, label: item.label }))}
        onChange={(event) => set("target", event.target.value)}
      />
      <Select
        label="من يراه"
        name="audience"
        value={draft.audience}
        options={audiences.map((item) => ({ value: item.id, label: item.label }))}
        onChange={(event) => set("audience", event.target.value)}
      />
      <TextField label="الصف" name="row" type="number" hint="الأزرار ذات الصف نفسه تظهر جنباً إلى جنب." value={draft.row} required onChange={(event) => set("row", event.target.value)} />
      <TextField label="الترتيب في الصف" name="position" type="number" value={draft.position} required onChange={(event) => set("position", event.target.value)} />
      <Select
        label="اللون"
        name="style"
        value={draft.style}
        options={[
          { value: "", label: "بلا لون" },
          { value: "danger", label: "أحمر" },
          { value: "primary", label: "أزرق" },
          { value: "success", label: "أخضر" },
        ]}
        onChange={(event) => set("style", event.target.value)}
      />
      <Select
        label="الظهور"
        name="enabled"
        value={draft.enabled}
        options={[
          { value: "1", label: "ظاهر" },
          { value: "0", label: "مخفي" },
        ]}
        onChange={(event) => set("enabled", event.target.value)}
      />
      <NoticeLine notice={notice} />
      <div className="sheet__actions">
        <Button type="submit" loading={busy}>
          حفظ
        </Button>
        <Button variant="ghost" type="button" onClick={onCancel}>
          إلغاء
        </Button>
      </div>
    </form>
  )
}

function RemoveButton({
  button,
  onDone,
  onCancel,
}: {
  button: BotButton
  onDone: (notice: Notice) => void
  onCancel: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  const onConfirm = async () => {
    setBusy(true)
    const result = await apiRequest(`/api/telegram/buttons/${button.id}/`, { method: "DELETE" })
    setBusy(false)
    if (!result.ok) {
      setNotice({ tone: "error", text: failureText(result) })
      return
    }
    onDone({ tone: "ok", text: `تم حذف الزر ${button.label}.` })
  }
  return (
    <div className="confirm" role="alertdialog" aria-modal="false" aria-labelledby="remove-button-title">
      <p className="confirm__title" id="remove-button-title">
        حذف زر {button.label}؟
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
