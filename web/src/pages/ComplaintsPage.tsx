import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import {
  DataTable,
  FilterBar,
  StatusChip,
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
import {
  ALL_ROWS,
  Ledger,
  Loaded,
  NoticeLine,
  PAGE_SIZE,
  STATUS_OPTIONS,
  actionNotice,
  formatDateTime,
  useLoad,
  type Notice,
} from "./common"

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
  const [filters, setFilters] = useState<FilterValues>({})
  const [page, setPage] = useState(1)
  const [notice, setNotice] = useState<Notice>(null)
  const canFlag = user.role === "admin" || user.role === "governor"
  const isInspector = user.role === "inspector"
  const regionOptions = useRegionOptions(user)

  const { state, reload } = useLoad(
    () =>
      apiRequest<Page<ComplaintRow>>(
        withQuery("/api/complaints/", {
          status: filters.status,
          region: canFlag ? filters.region : undefined,
          page,
          page_size: PAGE_SIZE,
        }),
      ),
    [filters.status, filters.region, page],
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

  const bulkActions: BulkAction[] = canFlag
    ? [
        { id: "flag", label: "وضع علامة المتابعة", onRun: (ids) => runFlag("flag", ids.map(Number)) },
        { id: "unflag", label: "إزالة علامة المتابعة", onRun: (ids) => runFlag("unflag", ids.map(Number)) },
      ]
    : []

  const rowActions = isInspector
    ? (row: ComplaintRow): RowAction[] =>
        row.status === "واردة" ? [{ id: "accept", label: "قبول", onSelect: () => accept(row.id) }] : []
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
          { key: "source", header: "القناة", render: (row: ComplaintRow) => (row.source === "telegram" ? "تلغرام" : "الموقع") },
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
        onChange={(values) => {
          setFilters(values)
          setPage(1)
        }}
      />
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
    </div>
  )
}
