import { useEffect, useMemo, useState, type FormEvent } from "react"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom"
import {
  Button,
  DataTable,
  Dialog,
  FilterBar,
  StatusChip,
  TextArea,
  type BulkAction,
  type Column,
  type FilterField,
  type FilterValues,
  type RowAction,
} from "../design-system"
import {
  apiRequest,
  postComplaintAction,
  withQuery,
  type ComplaintRow,
  type Page,
  type Place,
  type RegionPlace,
  type SessionUser,
} from "../api"
import { APP_ROUTES, canOpen } from "../routes"
import {
  ALL_ROWS,
  Ledger,
  Loaded,
  NoticeLine,
  PAGE_SIZE,
  STATUS_OPTIONS,
  actionNotice,
  failureText,
  formatDateTime,
  useLoad,
  type Notice,
} from "./common"
import { COMPLAINT_RECEIVED, ComplaintForm } from "./PublicPage"

const rowId = (row: ComplaintRow) => row.id

/** Region choices for the filter: admin sees every region, governor sees the regions of the own governorate. */
function useRegionOptions(user: SessionUser) {
  const [options, setOptions] = useState<{ value: string; label: string }[]>([])
  useEffect(() => {
    let cancelled = false
    if (user.role === "admin") {
      Promise.all([
        apiRequest<Page<RegionPlace>>(withQuery("/api/regions/", { page_size: ALL_ROWS })),
        apiRequest<Page<Place>>(withQuery("/api/governorates/", { page_size: ALL_ROWS })),
      ]).then(([regions, governorates]) => {
        if (cancelled || !regions.ok || !regions.data) return
        const names = new Map((governorates.data?.results ?? []).map((g) => [g.id, g.name]))
        setOptions(
          regions.data.results.map((r) => ({
            value: String(r.id),
            label: names.has(r.governorate) ? `${r.name} · ${names.get(r.governorate)}` : r.name,
          })),
        )
      })
    } else if (user.role === "governor" && user.governorate) {
      apiRequest<Page<RegionPlace>>(
        withQuery("/api/regions/public/", { governorate: user.governorate, page_size: ALL_ROWS }),
      ).then((result) => {
        if (!cancelled && result.ok && result.data)
          setOptions(result.data.results.map((r) => ({ value: String(r.id), label: r.name })))
      })
    }
    return () => {
      cancelled = true
    }
  }, [user.role, user.governorate])
  return options
}

export function ComplaintsPage({ user }: { user: SessionUser }) {
  const [params] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [filters, setFilters] = useState<FilterValues>({ status: params.get("status") || undefined })
  const [page, setPage] = useState(1)
  const [notice, setNotice] = useState<Notice>(null)
  const [filing, setFiling] = useState(false)
  const [returning, setReturning] = useState<ComplaintRow | null>(null)
  const [reason, setReason] = useState("")
  const [reasonError, setReasonError] = useState<string | undefined>()
  const [returningBusy, setReturningBusy] = useState(false)
  const canFlag = user.role === "admin" || user.role === "governor"
  const missions = APP_ROUTES.find((route) => route.id === "field-missions")
  const showMissions = missions ? canOpen(missions, user) : false
  const isInspector = user.role === "inspector"
  const regionOptions = useRegionOptions(user)

  useEffect(() => {
    const incoming = (location.state as { notice?: Notice } | null)?.notice
    if (!incoming) return
    setNotice(incoming)
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null })
  }, [location.pathname, location.search, location.state, navigate])

  const { state, reload } = useLoad(
    () =>
      apiRequest<Page<ComplaintRow>>(
        withQuery("/api/complaints/", {
          status: filters.status,
          region: canFlag ? filters.region : undefined,
          flagged: params.get("flagged") === "1" ? "1" : undefined,
          created_from: params.get("created_from") || undefined,
          created_to: params.get("created_to") || undefined,
          closed_from: params.get("closed_from") || undefined,
          closed_to: params.get("closed_to") || undefined,
          page,
          page_size: PAGE_SIZE,
        }),
      ),
    [filters.status, filters.region, page, params],
  )

  const schema = useMemo<FilterField[]>(() => {
    const fields: FilterField[] = [{ type: "select", key: "status", label: "الحالة", options: STATUS_OPTIONS }]
    if (canFlag) fields.push({ type: "select", key: "region", label: "المنطقة", options: regionOptions })
    return fields
  }, [canFlag, regionOptions])

  const runFlag = async (action: "flag" | "unflag", ids: number[]) => {
    setNotice(null)
    const result = await postComplaintAction(action, ids)
    setNotice(actionNotice(result, action === "flag" ? "تم وضع علامة المتابعة." : "تمت إزالة علامة المتابعة."))
    reload()
  }

  const accept = async (id: number) => {
    setNotice(null)
    const result = await postComplaintAction("accept", [id])
    setNotice(actionNotice(result, "تم قبول الشكوى، وهي الآن قيد المتابعة الميدانية."))
    reload()
  }

  const submitReturn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!returning) return
    if (!reason.trim()) {
      setReasonError("سبب الرفض مطلوب.")
      return
    }
    setReasonError(undefined)
    setReturningBusy(true)
    const result = await apiRequest(`/api/complaints/${returning.id}/return/`, {
      method: "POST",
      body: { reason: reason.trim() },
    })
    setReturningBusy(false)
    if (result.ok) {
      setReturning(null)
      setReason("")
      setNotice({ tone: "ok", text: "تم إرجاع الشكوى إلى مدير المحافظة." })
      reload()
    } else {
      setNotice({ tone: "error", text: failureText(result) })
    }
  }

  const bulkActions: BulkAction[] = canFlag
    ? [
        { id: "flag", label: "وضع علامة المتابعة", onRun: (ids) => runFlag("flag", ids.map(Number)) },
        { id: "unflag", label: "إزالة علامة المتابعة", onRun: (ids) => runFlag("unflag", ids.map(Number)) },
      ]
    : []

  const rowActions = isInspector
    ? (row: ComplaintRow): RowAction[] =>
        row.status === "واردة"
          ? [
              { id: "accept", label: "قبول", onSelect: () => accept(row.id) },
              {
                id: "return",
                label: "رفض وإرجاع للمدير",
                onSelect: () => {
                  setReason("")
                  setReasonError(undefined)
                  setReturning(row)
                },
              },
            ]
          : []
    : undefined

  const columns: Column<ComplaintRow>[] = [
    { key: "id", header: "الرقم", width: 72, render: (row) => <span className="app-num">{row.id}</span> },
    {
      key: "title",
      header: "العنوان",
      render: (row) => (
        <Link className="app-link" to={`/complaints/${row.id}/`}>
          {row.title}
        </Link>
      ),
    },
    { key: "governorate", header: "المحافظة", render: (row) => row.governorate_name },
    { key: "region", header: "المنطقة", render: (row) => row.region_name },
    { key: "status", header: "الحالة", render: (row) => <StatusChip status={row.status} /> },
    { key: "inspector", header: "المفتش", render: (row) => row.inspector_name || "—" },
    { key: "created_at", header: "وقت التقديم", render: (row) => formatDateTime(row.created_at) },
    ...(isInspector
      ? [
          { key: "source", header: "القناة", render: (row: ComplaintRow) => (row.source === "telegram" ? "تلغرام" : row.source === "whatsapp" ? "واتساب" : "الموقع") },
          {
            key: "contact",
            header: "مقدّم الشكوى",
            render: (row: ComplaintRow) => row.telegram_user_id || row.submitter_ip || "—",
          },
          { key: "field_replied_at", header: "وقت الرد الميداني", render: (row: ComplaintRow) => formatDateTime(row.field_replied_at) },
        ]
      : []),
    {
      key: "flag",
      header: "المتابعة",
      render: (row) => (row.is_flagged ? <span className="app-flag">عليها علامة</span> : "—"),
    },
  ]

  return (
    <div className="page">
      <div className="page__bar">
        <Button onClick={() => setFiling(true)}>تقديم شكوى</Button>
      </div>
      {returning && (
        <Dialog
          title="رفض وإرجاع للمدير"
          onClose={() => {
            setReturning(null)
            setReason("")
          }}
        >
          <form className="sheet__form" onSubmit={submitReturn} noValidate>
            <TextArea
              label="سبب الرفض"
              name="reason"
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              error={reasonError}
              required
            />
            <div className="sheet__actions">
              <Button type="submit" variant="danger" loading={returningBusy}>
                إرجاع للمدير
              </Button>
            </div>
          </form>
        </Dialog>
      )}
      {filing && (
        <Dialog title="تقديم شكوى" onClose={() => setFiling(false)}>
          <p className="account__note">الصورة اختيارية. بعد الإرسال تظهر جملة الاستلام فقط.</p>
          <ComplaintForm
            onSubmitted={() => {
              setFiling(false)
              setNotice({ tone: "ok", text: COMPLAINT_RECEIVED })
              setPage(1)
              reload()
            }}
          />
        </Dialog>
      )}
      {isInspector && (
        <Ledger
          label="بيانات المفتش"
          figures={[
            { key: "name", label: "المفتش", value: user.display_name || user.username },
            { key: "governorate", label: "المحافظة", value: user.governorate_name ?? "—" },
            { key: "region", label: "المنطقة", value: user.region_name ?? "—" },
          ]}
        />
      )}
      <FilterBar
        schema={schema}
        initialValues={{ status: params.get("status") || undefined }}
        onChange={(values) => {
          setFilters(values)
          setPage(1)
        }}
      />
      {(params.get("created_from") || params.get("closed_from") || params.get("flagged") === "1") && (
        <p className="ov-range">
          {params.get("flagged") === "1" && "المعلّمة فقط. "}
          {params.get("created_from") && `تاريخ التقديم ${params.get("created_from")} → ${params.get("created_to")}. `}
          {params.get("closed_from") && `تاريخ الإغلاق ${params.get("closed_from")} → ${params.get("closed_to")}.`}
        </p>
      )}
      <NoticeLine notice={notice} />
      <Loaded state={state} onRetry={reload}>
        {(data) => (
          <DataTable
            caption="قائمة الشكاوى"
            columns={columns}
            rows={data.results}
            getRowId={rowId}
            getRowLabel={(row) => row.title}
            rowActions={rowActions}
            bulkActions={bulkActions}
            emptyTitle="لا توجد شكاوى مطابقة."
            pagination={{ page: data.page, pageSize: data.page_size, total: data.count, onPageChange: setPage }}
          />
        )}
      </Loaded>
      {showMissions && (
        <div className="page__bar">
          <a className="ds-btn" data-variant="secondary" href="/field-missions/">
            مهمات ميدانية
          </a>
        </div>
      )}
    </div>
  )
}
