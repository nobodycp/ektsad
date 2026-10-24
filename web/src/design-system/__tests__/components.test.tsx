import { render, screen, fireEvent } from "@testing-library/react"
import * as DS from "../index"
import { tokens } from "../tokens"

const REQUIRED = [
  "AppShell",
  "Button",
  "TextField",
  "Select",
  "TextArea",
  "FileField",
  "FilterBar",
  "DataTable",
  "BulkActionBar",
  "RowActions",
  "StatusChip",
  "Timeline",
  "EmptyState",
  "LoadingState",
  "ErrorState",
] as const

describe("design system exports", () => {
  it.each(REQUIRED)("exports %s", (name) => {
    expect(DS[name]).toBeTypeOf("function")
  })
})

describe("tokens", () => {
  it("uses the exact palette", () => {
    expect(tokens.color).toMatchObject({
      paper: "#fafaf8",
      ink: "#0a0a0a",
      line: "#ececea",
      cedar: "#0a7a3e",
      copper: "#d00000",
      danger: "#b91c1c",
      sidebarBg: "#ffffff",
      sidebarText: "#0a0a0a",
      sidebarActive: "rgba(208, 0, 0, 0.1)",
    })
  })

  it("uses the exact spacing and radii", () => {
    expect(tokens.space).toEqual([4, 8, 12, 16, 24, 32, 48])
    expect(tokens.radius).toEqual({ input: 6, panel: 10 })
    expect(tokens.focusRing).toBe("2px solid #0a0a0a")
    expect(tokens.font.family).toContain("IBM Plex Sans Arabic")
    expect(tokens.font.family).not.toContain("Inter")
  })
})

describe("AppShell", () => {
  it("is rtl and marks the active nav item", () => {
    const { container } = render(
      <DS.AppShell
        title="منظومة المتابعة"
        nav={[
          { id: "reports", label: "البلاغات", href: "#reports" },
          { id: "users", label: "المستخدمون", href: "#users" },
        ]}
        activeId="reports"
      >
        <p>المحتوى</p>
      </DS.AppShell>,
    )
    expect(container.firstChild).toHaveAttribute("dir", "rtl")
    expect(container.firstChild).toHaveAttribute("lang", "ar")
    expect(screen.getByRole("link", { name: "البلاغات" })).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("link", { name: "المستخدمون" })).not.toHaveAttribute("aria-current")
    expect(screen.getByRole("main")).toHaveTextContent("المحتوى")
  })
})

describe("form controls", () => {
  it("labels TextField, Select, TextArea and FileField", () => {
    render(
      <>
        <DS.TextField label="الاسم" />
        <DS.Select label="المحافظة" options={[{ value: "1", label: "الجيزة" }]} placeholder="اختر" />
        <DS.TextArea label="الملاحظات" />
        <DS.FileField label="المرفقات" />
      </>,
    )
    expect(screen.getByLabelText("الاسم")).toHaveAttribute("type", "text")
    expect(screen.getByLabelText("المحافظة").tagName).toBe("SELECT")
    expect(screen.getByLabelText("الملاحظات").tagName).toBe("TEXTAREA")
    expect(screen.getByLabelText("المرفقات")).toHaveAttribute("type", "file")
  })

  it("wires error text to aria-describedby", () => {
    render(<DS.TextField label="الرقم القومي" error="الحقل مطلوب" />)
    const input = screen.getByLabelText("الرقم القومي")
    expect(input).toHaveAttribute("aria-invalid", "true")
    expect(input).toHaveAccessibleDescription("الحقل مطلوب")
  })

  it("Button supports variants and disabled loading", () => {
    const onClick = vi.fn()
    render(
      <>
        <DS.Button onClick={onClick}>حفظ</DS.Button>
        <DS.Button variant="danger" loading>
          حذف
        </DS.Button>
      </>,
    )
    fireEvent.click(screen.getByRole("button", { name: "حفظ" }))
    expect(onClick).toHaveBeenCalled()
    expect(screen.getByRole("button", { name: /حذف/ })).toBeDisabled()
    expect(screen.getByRole("button", { name: /حذف/ })).toHaveAttribute("data-variant", "danger")
  })
})

describe("RowActions", () => {
  it("renders an action button per item", () => {
    const onSelect = vi.fn()
    render(<DS.RowActions actions={[{ id: "edit", label: "تعديل", onSelect }]} />)
    fireEvent.click(screen.getByRole("button", { name: "تعديل" }))
    expect(onSelect).toHaveBeenCalled()
  })
})

describe("Timeline", () => {
  it("renders events in order as a list", () => {
    render(
      <DS.Timeline
        events={[
          { id: "1", title: "تم استلام البلاغ", at: "2026-01-01" },
          { id: "2", title: "إحالة إلى المفتش", at: "2026-01-02", actor: "أحمد" },
        ]}
      />,
    )
    const items = screen.getAllByRole("listitem")
    expect(items).toHaveLength(2)
    expect(items[0]).toHaveTextContent("تم استلام البلاغ")
    expect(items[1]).toHaveTextContent("أحمد")
  })
})

describe("states", () => {
  it("EmptyState, LoadingState and ErrorState render accessible messages", () => {
    const onRetry = vi.fn()
    render(
      <>
        <DS.EmptyState title="لا توجد بلاغات" />
        <DS.LoadingState />
        <DS.ErrorState message="تعذر التحميل" onRetry={onRetry} />
      </>,
    )
    expect(screen.getByText("لا توجد بلاغات")).toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent("جار التحميل")
    expect(screen.getByRole("alert")).toHaveTextContent("تعذر التحميل")
    fireEvent.click(screen.getByRole("button", { name: "إعادة المحاولة" }))
    expect(onRetry).toHaveBeenCalled()
  })
})
