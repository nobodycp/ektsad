import { useEffect, useMemo, useState } from "react"
import {
  DataTable,
  FilterBar,
  STATUS_LABELS,
  StatusChip,
  TextField,
  type Column,
  type FilterField,
  type FilterValues,
} from "../design-system"
import { apiRequest, withQuery, type Page, type UserRow } from "../api"
import { ALL_ROWS, Ledger, Loaded, STATUS_OPTIONS, Section, todayInHebron, useLoad } from "./common"
import { optionsOf, useAdminGeography } from "./geo"

type GovernorReport = { date: string; done: number; pending: number; done_by_inspector: Record<string, number> }

type Average = { hours: number; minutes: number } | null

type InspectorStats = { id: number; name: string; accepted: number; done: number; pending: number; average: Average }

type AdminReport = {
  complaints: { count: number; by_status: Record<string, number> }
  inspectors: InspectorStats[]
  legal: { referred: number; resolved: number; still_legal: number }
  publications: { prices: number; crossings: number }
}

export function formatAverage(average: Average): string {
  if (!average) return "—"
  return `${average.hours} ساعة و${average.minutes} دقيقة`
}

type DoneRow = { name: string; count: number }
const doneRowId = (row: DoneRow) => row.name
const DONE_COLUMNS: Column<DoneRow>[] = [
  { key: "name", header: "المفتش", render: (row) => row.name || "—" },
  { key: "count", header: "المنجز", render: (row) => <span className="app-num">{row.count}</span> },
]

export function GovernorReportPage() {
  const [day, setDay] = useState(todayInHebron)
  const { state, reload } = useLoad(
    () => apiRequest<GovernorReport>(withQuery("/api/governor/report/", { date: day })),
    [day],
  )

  return (
    <div className="page">
      <div className="page__bar">
        <TextField label="اليوم" type="date" name="date" value={day} onChange={(e) => setDay(e.target.value)} />
      </div>
      <Loaded state={state} onRetry={reload}>
        {(report) => (
          <>
            <Ledger
              label="ملخص اليوم"
              figures={[
                { key: "done", label: "المنجز", value: report.done },
                { key: "pending", label: "المعلق", value: report.pending },
              ]}
            />
            <Section title="المنجز لكل مفتش">
              <DataTable
                caption="المنجز لكل مفتش"
                columns={DONE_COLUMNS}
                rows={Object.entries(report.done_by_inspector).map(([name, count]) => ({ name, count }))}
                getRowId={doneRowId}
                emptyTitle="لا يوجد منجز في هذا اليوم."
              />
            </Section>
          </>
        )}
      </Loaded>
    </div>
  )
}

const inspectorRowId = (row: InspectorStats) => row.id
const INSPECTOR_COLUMNS: Column<InspectorStats>[] = [
  { key: "name", header: "المفتش", render: (row) => row.name },
  { key: "accepted", header: "المقبول", render: (row) => <span className="app-num">{row.accepted}</span> },
  { key: "done", header: "المنجز", render: (row) => <span className="app-num">{row.done}</span> },
  { key: "pending", header: "المعلق", render: (row) => <span className="app-num">{row.pending}</span> },
  { key: "average", header: "متوسط زمن الكشف", render: (row) => formatAverage(row.average) },
]

function useInspectorOptions() {
  const [options, setOptions] = useState<{ value: string; label: string }[]>([])
  useEffect(() => {
    let cancelled = false
    apiRequest<Page<UserRow>>(withQuery("/api/users/", { role: "inspector", page_size: ALL_ROWS })).then((result) => {
      if (!cancelled && result.ok && result.data)
        setOptions(result.data.results.map((u) => ({ value: String(u.id), label: u.display_name || u.username })))
    })
    return () => {
      cancelled = true
    }
  }, [])
  return options
}

export function AdminReportsPage() {
  const [filters, setFilters] = useState<FilterValues>({})
  const geo = useAdminGeography()
  const inspectors = useInspectorOptions()

  const { state, reload } = useLoad(
    () =>
      apiRequest<AdminReport>(
        withQuery("/api/reports/", {
          date_from: filters.date_from,
          date_to: filters.date_to,
          governorate: filters.governorate,
          region: filters.region,
          status: filters.status,
          inspector: filters.inspector,
        }),
      ),
    [filters.date_from, filters.date_to, filters.governorate, filters.region, filters.status, filters.inspector],
  )

  const schema = useMemo<FilterField[]>(() => {
    const regions = filters.governorate
      ? geo.regions.filter((r) => String(r.governorate) === filters.governorate)
      : geo.regions
    return [
      { type: "date_range", key: "period", label: "الفترة" },
      { type: "select", key: "governorate", label: "المحافظة", options: optionsOf(geo.governorates) },
      { type: "select", key: "region", label: "المنطقة", options: optionsOf(regions) },
      { type: "select", key: "status", label: "الحالة الحالية", options: STATUS_OPTIONS },
      { type: "select", key: "inspector", label: "المفتش", options: inspectors },
    ]
  }, [geo, filters.governorate, inspectors])

  return (
    <div className="page">
      <FilterBar schema={schema} onChange={setFilters} />
      <p className="app-muted">الفترة الفارغة تعني اليوم فقط. فلتر الحالة يخص بلوك الشكاوى وحده، وبلوك النشر يتأثر بالفترة فقط.</p>
      <Loaded state={state} onRetry={reload}>
        {(report) => (
          <>
            <Section title="الشكاوى" note="المقدّمة داخل الفترة، موزعة حسب الحالة الحالية.">
              <Ledger
                label="الشكاوى حسب الحالة"
                figures={[
                  { key: "count", label: "المجموع", value: report.complaints.count },
                  ...STATUS_LABELS.map((status) => ({
                    key: status,
                    label: <StatusChip status={status} />,
                    value: report.complaints.by_status[status] ?? 0,
                  })),
                ]}
              />
            </Section>
            <Section title="أداء المفتشين" note="المتوسط من القبول حتى سطر المتابعة الميدانية.">
              <DataTable
                caption="أداء المفتشين"
                columns={INSPECTOR_COLUMNS}
                rows={report.inspectors}
                getRowId={inspectorRowId}
                emptyTitle="لا يوجد مفتشون مطابقون."
              />
            </Section>
            <Section title="الشؤون القانونية">
              <Ledger
                label="أداء الشؤون القانونية"
                figures={[
                  { key: "referred", label: "المحوّل", value: report.legal.referred },
                  { key: "resolved", label: "تم الانجاز", value: report.legal.resolved },
                  { key: "still_legal", label: "ما زال في الشؤون القانونية", value: report.legal.still_legal },
                ]}
              />
            </Section>
            <Section title="النشر">
              <Ledger
                label="النشر في الفترة"
                figures={[
                  { key: "prices", label: "قوائم الأسعار", value: report.publications.prices },
                  { key: "crossings", label: "حركة المعابر", value: report.publications.crossings },
                ]}
              />
            </Section>
          </>
        )}
      </Loaded>
    </div>
  )
}
