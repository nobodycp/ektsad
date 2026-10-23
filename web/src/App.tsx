import { useState } from "react"
import {
  AppShell,
  Button,
  DataTable,
  FilterBar,
  STATUS_LABELS,
  StatusChip,
  Timeline,
  type Column,
  type FilterValues,
} from "./design-system"

type Report = { id: number; number: string; governorate: string; status: string; date: string }

const sample: Report[] = STATUS_LABELS.map((status, i) => ({
  id: i + 1,
  number: `BL-2026-${String(i + 101).padStart(4, "0")}`,
  governorate: ["القاهرة", "الجيزة", "الإسكندرية", "أسيوط", "المنيا"][i],
  status,
  date: `2026-10-${String(10 + i).padStart(2, "0")}`,
}))

const columns: Column<Report>[] = [
  { key: "number", header: "رقم البلاغ", render: (r) => r.number },
  { key: "governorate", header: "المحافظة", render: (r) => r.governorate },
  { key: "status", header: "الحالة", render: (r) => <StatusChip status={r.status} /> },
  { key: "date", header: "التاريخ", render: (r) => r.date },
]

export function App() {
  const [, setFilters] = useState<FilterValues>({})
  return (
    <AppShell
      title="منظومة المتابعة"
      subtitle="الإدارة العامة للتفتيش"
      nav={[
        { id: "reports", label: "البلاغات", href: "#" },
        { id: "inspectors", label: "المفتشون", href: "#" },
        { id: "users", label: "المستخدمون", href: "#" },
      ]}
      activeId="reports"
      pageTitle="البلاغات"
      headerActions={<Button>بلاغ جديد</Button>}
    >
      <FilterBar
        onChange={setFilters}
        schema={[
          { type: "search", key: "q", label: "بحث", placeholder: "رقم البلاغ أو الاسم" },
          {
            type: "select",
            key: "status",
            label: "الحالة",
            options: STATUS_LABELS.map((s) => ({ value: s, label: s })),
          },
          { type: "date_range", key: "date", label: "الفترة" },
        ]}
      />
      <DataTable
        columns={columns}
        rows={sample}
        getRowId={(r) => r.id}
        rowActions={() => [{ id: "open", label: "فتح", onSelect: () => {} }]}
        bulkActions={[{ id: "assign", label: "إحالة إلى مفتش", onRun: () => {} }]}
        pagination={{ page: 1, pageSize: 20, total: sample.length, onPageChange: () => {} }}
      />
      <Timeline
        events={[
          { id: "1", title: "تم استلام البلاغ", at: "2026-10-10" },
          { id: "2", title: "إحالة إلى المتابعة الميدانية", at: "2026-10-11", actor: "م. أحمد سالم" },
        ]}
      />
    </AppShell>
  )
}
