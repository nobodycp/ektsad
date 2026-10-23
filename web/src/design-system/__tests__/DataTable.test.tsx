import { render, screen, fireEvent, within } from "@testing-library/react"
import { DataTable, type Column } from "../index"

type Row = { id: number; name: string; status: string }

const rows: Row[] = [
  { id: 1, name: "بلاغ أول", status: "واردة" },
  { id: 2, name: "بلاغ ثان", status: "منتهية" },
]
const columns: Column<Row>[] = [
  { key: "name", header: "الاسم", render: (r) => r.name },
  { key: "status", header: "الحالة", render: (r) => r.status },
]

describe("DataTable", () => {
  it("renders columns and rows", () => {
    render(<DataTable columns={columns} rows={rows} getRowId={(r) => r.id} />)
    expect(screen.getByRole("columnheader", { name: "الاسم" })).toBeInTheDocument()
    expect(screen.getByText("بلاغ أول")).toBeInTheDocument()
    expect(screen.getByText("بلاغ ثان")).toBeInTheDocument()
  })

  it("does not render BulkActionBar when bulkActions is empty", () => {
    render(<DataTable columns={columns} rows={rows} getRowId={(r) => r.id} bulkActions={[]} />)
    expect(screen.queryByTestId("bulk-action-bar")).not.toBeInTheDocument()
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument()
  })

  it("does not render BulkActionBar when bulkActions is omitted", () => {
    render(<DataTable columns={columns} rows={rows} getRowId={(r) => r.id} />)
    expect(screen.queryByTestId("bulk-action-bar")).not.toBeInTheDocument()
  })

  it("shows BulkActionBar after selecting rows and passes selected ids", () => {
    const onRun = vi.fn()
    render(
      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(r) => r.id}
        bulkActions={[{ id: "close", label: "إنهاء المحدد", onRun }]}
      />,
    )
    fireEvent.click(screen.getByRole("checkbox", { name: "تحديد بلاغ أول" }))
    const bar = screen.getByTestId("bulk-action-bar")
    expect(within(bar).getByText("تم تحديد 1")).toBeInTheDocument()
    fireEvent.click(within(bar).getByRole("button", { name: "إنهاء المحدد" }))
    expect(onRun).toHaveBeenCalledWith([1])
  })

  it("selects all rows from the header checkbox", () => {
    const onRun = vi.fn()
    render(
      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(r) => r.id}
        bulkActions={[{ id: "close", label: "إنهاء", onRun }]}
      />,
    )
    fireEvent.click(screen.getByRole("checkbox", { name: "تحديد الكل" }))
    fireEvent.click(screen.getByRole("button", { name: "إنهاء" }))
    expect(onRun).toHaveBeenCalledWith([1, 2])
  })

  it("renders row actions per row", () => {
    const onSelect = vi.fn()
    render(
      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(r) => r.id}
        rowActions={(row) => [{ id: "open", label: `فتح ${row.name}`, onSelect: () => onSelect(row.id) }]}
      />,
    )
    fireEvent.click(screen.getByRole("button", { name: "فتح بلاغ ثان" }))
    expect(onSelect).toHaveBeenCalledWith(2)
  })

  it("renders pagination and moves pages", () => {
    const onPageChange = vi.fn()
    render(
      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(r) => r.id}
        pagination={{ page: 1, pageSize: 2, total: 5, onPageChange }}
      />,
    )
    expect(screen.getByText("صفحة 1 من 3")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "السابق" })).toBeDisabled()
    fireEvent.click(screen.getByRole("button", { name: "التالي" }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it("shows the empty state when there are no rows", () => {
    render(<DataTable columns={columns} rows={[]} getRowId={(r) => r.id} />)
    expect(screen.getByText("لا توجد بيانات")).toBeInTheDocument()
  })
})
