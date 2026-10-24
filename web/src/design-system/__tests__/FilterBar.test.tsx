import { render, screen, fireEvent } from "@testing-library/react"
import { FilterBar, FILTER_QUERY_KEYS, type FilterField } from "../index"

const schema: FilterField[] = [
  { type: "search", key: "q", label: "بحث" },
  {
    type: "select",
    key: "status",
    label: "الحالة",
    options: [
      { value: "incoming", label: "واردة" },
      { value: "done", label: "منتهية" },
    ],
  },
  {
    type: "select",
    key: "governorate",
    label: "المحافظة",
    options: [{ value: "cairo", label: "القاهرة" }],
  },
  { type: "date_range", key: "date", label: "الفترة" },
]

describe("FilterBar", () => {
  it("renders a control per schema field", () => {
    render(<FilterBar schema={schema} onChange={() => {}} />)
    expect(screen.getByLabelText("بحث")).toBeInTheDocument()
    expect(screen.getByLabelText("الحالة")).toBeInTheDocument()
    expect(screen.getByLabelText("المحافظة")).toBeInTheDocument()
    expect(screen.getByLabelText("من تاريخ")).toBeInTheDocument()
    expect(screen.getByLabelText("إلى تاريخ")).toBeInTheDocument()
  })

  it("emits the documented query keys", () => {
    const onChange = vi.fn()
    render(<FilterBar schema={schema} onChange={onChange} />)

    fireEvent.change(screen.getByLabelText("بحث"), { target: { value: "مخالفة" } })
    expect(onChange).toHaveBeenLastCalledWith({ q: "مخالفة" })

    fireEvent.change(screen.getByLabelText("الحالة"), { target: { value: "done" } })
    expect(onChange).toHaveBeenLastCalledWith({ q: "مخالفة", status: "done" })

    fireEvent.change(screen.getByLabelText("من تاريخ"), { target: { value: "2026-01-01" } })
    fireEvent.change(screen.getByLabelText("إلى تاريخ"), { target: { value: "2026-02-01" } })
    expect(onChange).toHaveBeenLastCalledWith({
      q: "مخالفة",
      status: "done",
      date_from: "2026-01-01",
      date_to: "2026-02-01",
    })
  })

  it("drops a key when its value is cleared", () => {
    const onChange = vi.fn()
    render(<FilterBar schema={schema} onChange={onChange} initialValues={{ q: "x", governorate: "cairo" }} />)
    fireEvent.change(screen.getByLabelText("بحث"), { target: { value: "" } })
    expect(onChange).toHaveBeenLastCalledWith({ governorate: "cairo" })
  })

  it("resets all filters", () => {
    const onChange = vi.fn()
    render(<FilterBar schema={schema} onChange={onChange} initialValues={{ q: "x" }} />)
    fireEvent.click(screen.getByRole("button", { name: "مسح الفلاتر" }))
    expect(onChange).toHaveBeenLastCalledWith({})
  })

  it("lists the supported query keys", () => {
    expect([...FILTER_QUERY_KEYS]).toEqual([
      "q",
      "status",
      "governorate",
      "region",
      "inspector",
      "date_from",
      "date_to",
      "role",
      "is_active",
      "kind",
    ])
  })

  it("supports a single date field mapped to date_from", () => {
    const onChange = vi.fn()
    render(<FilterBar schema={[{ type: "date", key: "date_from", label: "التاريخ" }]} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText("التاريخ"), { target: { value: "2026-03-03" } })
    expect(onChange).toHaveBeenLastCalledWith({ date_from: "2026-03-03" })
  })
})
