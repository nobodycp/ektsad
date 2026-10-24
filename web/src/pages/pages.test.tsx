import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ReactNode } from "react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, beforeEach, vi } from "vitest"
import type { ComplaintRow, SessionUser, UserRow } from "../api"
import { ComplaintPage } from "./ComplaintPage"
import { ComplaintsPage } from "./ComplaintsPage"
import { FieldMissionPage } from "./FieldMissionPage"
import { FieldMissionsPage } from "./FieldMissionsPage"
import { PublicPage } from "./PublicPage"
import { TelegramHealthPage } from "./TelegramHealthPage"
import { RolesPage } from "./RolesPage"
import { UsersPage } from "./UsersPage"

type Reply = { status: number; body: unknown }
type Handler = (url: string, init: RequestInit) => Reply | undefined

function mockFetch(handler: Handler) {
  const fn = vi.fn(async (url: string, init: RequestInit = {}) => {
    const reply = handler(url, init) ?? { status: 403, body: { detail: "Forbidden" } }
    return new Response(JSON.stringify(reply.body), {
      status: reply.status,
      headers: { "Content-Type": "application/json" },
    })
  })
  vi.stubGlobal("fetch", fn)
  return fn
}

const page = <T,>(results: T[]) => ({ status: 200, body: { count: results.length, page: 1, page_size: 20, results } })

function inRouter(node: ReactNode, path = "/") {
  return render(<MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>)
}

const field = (label: string) => screen.getByLabelText(new RegExp(`^${label}\\*?$`))

const base: SessionUser = {
  id: 1,
  username: "admin",
  display_name: "المدير",
  role: "admin",
  governorate: null,
  governorate_name: null,
  region: null,
  region_name: null,
  can_publish_prices: false,
  can_publish_crossings: false,
  can_view_all_complaints: false,
  can_open_field_missions: false,
  can_view_field_missions: false,
}

const complaint: ComplaintRow = {
  id: 7,
  governorate: 1,
  governorate_name: "محافظة تجريبية",
  region: 3,
  region_name: "المنطقة الأولى",
  title: "سعر الخبز مرتفع",
  body: "التفاصيل",
  status: "واردة",
  inspector: null,
  inspector_name: "",
  created_at: "2026-10-24T08:00:00+00:00",
  is_flagged: false,
}

let user: ReturnType<typeof userEvent.setup>

beforeEach(() => {
  user = userEvent.setup()
  document.cookie = "csrftoken=token-abc"
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT"
})

describe("public page", () => {
  function publicFetch(submitReply: Reply, latestPrice: Reply["body"] = { detail: "لا توجد قائمة أسعار منشورة." }) {
    return mockFetch((url, init) => {
      if (url.startsWith("/api/governorates/public/")) return page([{ id: 1, name: "محافظة تجريبية" }])
      if (url.startsWith("/api/regions/public/?governorate=1"))
        return page([{ id: 3, governorate: 1, name: "المنطقة الأولى" }])
      if (url === "/api/prices/latest/") return { status: 200, body: latestPrice }
      if (url === "/api/crossings/latest/") return { status: 200, body: { detail: "لا توجد حركة معابر منشورة." } }
      if (url === "/api/complaints/public/" && init.method === "POST") return submitReply
      return undefined
    })
  }

  async function fillAndSubmit() {
    await waitFor(() => expect(within(field("المحافظة")).getByRole("option", { name: "محافظة تجريبية" })).toBeInTheDocument())
    await user.selectOptions(field("المحافظة"), "1")
    await waitFor(() => expect(within(field("المنطقة")).getByRole("option", { name: "المنطقة الأولى" })).toBeInTheDocument())
    await user.selectOptions(field("المنطقة"), "3")
    await user.type(field("عنوان الشكوى"), "سعر الخبز")
    await user.type(field("محتوى الشكوى"), "البائع رفع السعر")
    await user.click(screen.getByRole("button", { name: "تقديم الشكوى" }))
  }

  it("submits a public complaint as multipart and shows the receipt without a number", async () => {
    const fetchFn = publicFetch({ status: 201, body: { detail: "تم استلام الشكوى." } })
    inRouter(<PublicPage />)
    await fillAndSubmit()

    expect(await screen.findByText("تم استلام الشكوى.")).toBeInTheDocument()
    expect(screen.queryByText(/رقم/)).not.toBeInTheDocument()

    const call = fetchFn.mock.calls.find(([url]) => url === "/api/complaints/public/")
    const init = call?.[1] as RequestInit
    expect(init.method).toBe("POST")
    expect(init.credentials).toBe("include")
    const headers = init.headers as Record<string, string>
    expect(headers["X-CSRFToken"]).toBe("token-abc")
    expect(headers["Content-Type"]).toBeUndefined()
    const form = init.body as FormData
    expect(form).toBeInstanceOf(FormData)
    expect(form.get("governorate")).toBe("1")
    expect(form.get("region")).toBe("3")
    expect(form.get("title")).toBe("سعر الخبز")
    expect(form.get("body")).toBe("البائع رفع السعر")
    expect(form.get("image")).toBeNull()
  })

  it("shows the rate limit message from the server", async () => {
    publicFetch({ status: 429, body: { detail: "تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً." } })
    inRouter(<PublicPage />)
    await fillAndSubmit()
    expect(await screen.findByRole("alert")).toHaveTextContent("تجاوزت الحد المسموح لتقديم الشكاوى. حاول لاحقاً.")
    expect(screen.queryByText("تم استلام الشكوى.")).not.toBeInTheDocument()
  })

  it("shows the empty price and crossing sentences when nothing is published", async () => {
    publicFetch({ status: 201, body: {} })
    inRouter(<PublicPage />)
    expect(await screen.findByText("لا توجد قائمة أسعار منشورة.")).toBeInTheDocument()
    expect(await screen.findByText("لا توجد حركة معابر منشورة.")).toBeInTheDocument()
    expect(screen.queryByRole("img")).not.toBeInTheDocument()
  })

  it("shows the latest price image from the public media path", async () => {
    publicFetch({ status: 201, body: {} }, { id: 4, published_at: "2026-10-24T08:00:00+00:00", publisher_name: "x", has_image: true })
    inRouter(<PublicPage />)
    const image = await screen.findByRole("img", { name: "قائمة الأسعار الحالية" })
    expect(image.getAttribute("src")).toMatch(/^\/api\/media\/prices\/latest\//)
    expect(screen.queryByText("لا توجد قائمة أسعار منشورة.")).not.toBeInTheDocument()
  })
})

describe("complaints list", () => {
  it("renders rows through DataTable with links and the inspector header", async () => {
    const fetchFn = mockFetch((url) => (url.startsWith("/api/complaints/?") ? page([complaint]) : undefined))
    const inspector: SessionUser = {
      ...base,
      id: 5,
      role: "inspector",
      display_name: "مفتش أول",
      governorate: 1,
      governorate_name: "محافظة تجريبية",
      region: 3,
      region_name: "المنطقة الأولى",
    }
    const { container } = inRouter(<ComplaintsPage user={inspector} />)

    const link = await screen.findByRole("link", { name: "سعر الخبز مرتفع" })
    expect(link).toHaveAttribute("href", "/complaints/7/")
    const tables = container.querySelectorAll("table")
    expect(tables).toHaveLength(1)
    expect(tables[0]).toHaveClass("ds-table")
    expect(tables[0].closest(".ds-table-panel")).not.toBeNull()

    const header = screen.getByLabelText("بيانات المفتش")
    expect(header).toHaveTextContent("مفتش أول")
    expect(header).toHaveTextContent("محافظة تجريبية")
    expect(header).toHaveTextContent("المنطقة الأولى")

    expect(screen.getByRole("button", { name: "قبول" })).toBeInTheDocument()
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument()
    expect(fetchFn.mock.calls[0][0]).toContain("page=1")
  })

  it("flags selected rows for a governor and refetches", async () => {
    let flagged = false
    const fetchFn = mockFetch((url, init) => {
      if (url.startsWith("/api/complaints/?")) return page([{ ...complaint, is_flagged: flagged }])
      if (url === "/api/complaints/actions/" && init.method === "POST") {
        flagged = true
        return { status: 200, body: { succeeded: [7], failed: [] } }
      }
      if (url.startsWith("/api/regions/public/")) return page([{ id: 3, governorate: 1, name: "المنطقة الأولى" }])
      return undefined
    })
    inRouter(<ComplaintsPage user={{ ...base, role: "governor", governorate: 1 }} />)
    await user.click(await screen.findByRole("checkbox", { name: "تحديد سعر الخبز مرتفع" }))
    await user.click(screen.getByRole("button", { name: "وضع علامة المتابعة" }))
    expect(await screen.findByText("عليها علامة")).toBeInTheDocument()
    const action = fetchFn.mock.calls.find(([url]) => url === "/api/complaints/actions/")
    expect(JSON.parse(String(action?.[1]?.body))).toEqual({ action: "flag", ids: [7] })
    expect(fetchFn.mock.calls.filter(([url]) => String(url).startsWith("/api/complaints/?"))).toHaveLength(2)
  })
})

describe("complaint page", () => {
  it("shows the second-accept message and keeps the follow-up timeline", async () => {
    mockFetch((url, init) => {
      if (url === "/api/complaints/7/")
        return {
          status: 200,
          body: {
            ...complaint,
            follow_ups: [
              { id: 1, author_name: "مفتش", created_at: "2026-10-24T09:00:00+00:00", place: "field", body: "تم الكشف", files: [] },
            ],
          },
        }
      if (url === "/api/complaints/actions/" && init.method === "POST")
        return { status: 200, body: { succeeded: [], failed: [{ id: 7, detail: "استلم هذه الشكوى مفتش آخر." }] } }
      return undefined
    })
    inRouter(
      <Routes>
        <Route path="/complaints/:id/" element={<ComplaintPage user={{ ...base, role: "inspector", id: 5 }} />} />
      </Routes>,
      "/complaints/7/",
    )
    expect(await screen.findByRole("region", { name: "نص الشكوى" })).toHaveTextContent("التفاصيل")
    expect(screen.getByText("لم تُستلم بعد")).toBeInTheDocument()
    expect(screen.getByText("محافظة تجريبية، المنطقة الأولى")).toBeInTheDocument()
    const timeline = await screen.findByRole("list", { name: "خط تقدم الشكوى" })
    expect(within(timeline).getByText("تم الكشف")).toBeInTheDocument()
    expect(within(timeline).getByText("التفاصيل")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "قبول الشكوى" }))
    expect(await screen.findByRole("alert")).toHaveTextContent("استلم هذه الشكوى مفتش آخر.")
  })
})

describe("users", () => {
  const staff: UserRow = {
    id: 9,
    username: "inspector1",
    display_name: "مفتش",
    role: "inspector",
    governorate: 1,
    region: 3,
    can_publish_prices: false,
    can_publish_crossings: false,
    can_view_all_complaints: false,
    can_login_web: true,
    can_open_field_missions: false,
    can_view_field_missions: false,
    is_active: true,
  }

  it("resets a password and shows the 16 characters once", async () => {
    const generated = "Ab3dEf6hIj9kLm2n"
    const fetchFn = mockFetch((url, init) => {
      if (url.startsWith("/api/users/?")) return page([staff])
      if (url === "/api/users/9/password/" && init.method === "POST") return { status: 200, body: { password: generated } }
      return undefined
    })
    inRouter(<UsersPage />)
    await user.click(await screen.findByRole("button", { name: "إجراءات" }))
    await user.click(screen.getByRole("menuitem", { name: "كلمة المرور" }))
    await user.click(screen.getByRole("button", { name: "إعادة تعيين كلمة المرور" }))

    const shown = await screen.findByTestId("revealed-password")
    expect(shown.textContent).toHaveLength(16)
    expect(screen.getAllByText(generated)).toHaveLength(1)
    const call = fetchFn.mock.calls.find(([url]) => url === "/api/users/9/password/")
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ mode: "reset" })

    await user.click(screen.getByRole("button", { name: "تم النقل، أخفِ الكلمة" }))
    expect(screen.queryByText(generated)).not.toBeInTheDocument()
  })

  it("deletes a user only after the confirmation", async () => {
    const fetchFn = mockFetch((url, init) => {
      if (url.startsWith("/api/users/?")) return page([staff])
      if (url === "/api/users/9/" && init.method === "DELETE") return { status: 200, body: { detail: "ok" } }
      return undefined
    })
    inRouter(<UsersPage />)
    await user.click(await screen.findByRole("button", { name: "إجراءات" }))
    await user.click(screen.getByRole("menuitem", { name: "حذف" }))
    expect(fetchFn.mock.calls.some(([url]) => url === "/api/users/9/")).toBe(false)
    const dialog = screen.getByRole("alertdialog")
    await user.click(within(dialog).getByRole("button", { name: "تأكيد الحذف" }))
    expect(await screen.findByText("تم حذف الحساب inspector1.")).toBeInTheDocument()
    expect(fetchFn.mock.calls.filter(([url]) => String(url).startsWith("/api/users/?")).length).toBeGreaterThan(1)
  })

  it("asks before entering another account", async () => {
    const session = {
      id: staff.id,
      username: staff.username,
      display_name: staff.display_name,
      role: "inspector",
      governorate: 1,
      governorate_name: "محافظة تجريبية",
      region: 3,
      region_name: "المنطقة الأولى",
      can_publish_prices: false,
      can_publish_crossings: false,
      can_view_all_complaints: false,
      impersonator: { id: 1, username: "admin", display_name: "المدير" },
    }
    const fetchFn = mockFetch((url, init) => {
      if (url.startsWith("/api/users/?")) return page([staff])
      if (url === "/api/users/9/enter/" && init.method === "POST") return { status: 200, body: session }
      return undefined
    })
    inRouter(<UsersPage />)
    await user.click(await screen.findByRole("button", { name: "إجراءات" }))
    await user.click(screen.getByRole("menuitem", { name: "دخول بالحساب" }))
    expect(fetchFn.mock.calls.some(([url]) => url === "/api/users/9/enter/")).toBe(false)
    const dialog = screen.getByRole("dialog", { name: "دخول بالحساب" })
    await user.click(within(dialog).getByRole("button", { name: "دخول بالحساب" }))
    expect(fetchFn.mock.calls.some(([url, init]) => url === "/api/users/9/enter/" && init?.method === "POST")).toBe(true)
  })
})

it("creates a role from the roles tab and keeps permissions on the role", async () => {
  const roles = [
    {
      id: 2,
      name: "مفتش",
      kind: "inspector",
      built_in: true,
      can_view_all_complaints: false,
      can_view_reports: false,
      can_manage_users: false,
      can_manage_geography: false,
      can_publish: false,
      can_field_missions: false,
      can_manage_settings: false,
      can_impersonate: false,
      can_login_web: true,
    },
  ]
  const fetchFn = mockFetch((url, init) => {
    if (url === "/api/roles/" && (!init.method || init.method === "GET")) return { status: 200, body: { results: roles } }
    if (url === "/api/roles/" && init.method === "POST") {
      return { status: 201, body: { ...roles[0], id: 8, name: "مساعد المدير", kind: "custom", built_in: false, can_manage_users: true } }
    }
    return undefined
  })
  inRouter(<RolesPage />)
  expect(screen.getByRole("link", { name: "الأدوار" })).toHaveAttribute("aria-current", "page")
  await user.click(screen.getByRole("button", { name: "دور جديد" }))
  await user.type(field("اسم الدور"), "مساعد المدير")
  await user.click(screen.getByRole("checkbox", { name: "المستخدمون" }))
  await user.click(screen.getByRole("button", { name: "إنشاء الدور" }))
  expect(await screen.findByText("تم إنشاء الدور.")).toBeInTheDocument()
  const call = fetchFn.mock.calls.find(([url, init]) => url === "/api/roles/" && init?.method === "POST")
  const body = JSON.parse(String(call?.[1]?.body))
  expect(body.name).toBe("مساعد المدير")
  expect(body.can_manage_users).toBe(true)
  expect(body.can_manage_settings).toBe(false)
})

it("shows an unregistered Telegram webhook to the system admin", async () => {
  mockFetch((url) =>
    url === "/api/telegram/health/"
      ? {
          status: 200,
          body: { registered: false, last_error: "تعذّر التسجيل", last_update_at: null, pending_count: 2, oldest_wait: null },
        }
      : undefined,
  )
  inRouter(<TelegramHealthPage />)
  expect(await screen.findByText("غير مسجّل")).toBeInTheDocument()
  expect(screen.getByText("تعذّر التسجيل")).toBeInTheDocument()
  expect(screen.getByText("2")).toBeInTheDocument()
})

describe("field missions", () => {
  const mission = {
    id: 4,
    kind: "ضبط",
    priority: "خطر",
    status: "عند إدارة المحافظة",
    details: "تفاصيل المهمة",
    place_name: "محل النور",
    phone: "0599000000",
    has_image: false,
    governorate: 1,
    governorate_name: "محافظة تجريبية",
    region: null,
    region_name: null,
    created_by_name: "مدير النظام",
    created_at: "2026-10-24T08:00:00+00:00",
    field_replied_at: null,
    legal_referred_at: null,
    closed_at: null,
    assignees: [],
    follow_ups: [],
  }

  it("asks for a priority and can address the governorate office", async () => {
    mockFetch((url) => {
      if (url.startsWith("/api/field-missions/")) return page([])
      if (url.startsWith("/api/governorates/")) return page([{ id: 1, name: "محافظة تجريبية" }])
      if (url.startsWith("/api/regions/")) return page([])
      return undefined
    })
    inRouter(<FieldMissionsPage user={{ ...base, can_view_field_missions: true }} />)
    await user.click(await screen.findByRole("button", { name: "مهمة جديدة" }))
    expect(screen.getByLabelText(/^الأولوية/)).toBeInTheDocument()
    expect(screen.getByRole("option", { name: "إدارة المحافظة" })).toBeInTheDocument()
  })

  it("links each mission to its own page", async () => {
    mockFetch((url) => (url.startsWith("/api/field-missions/") ? page([mission]) : undefined))
    inRouter(<FieldMissionsPage user={{ ...base, can_view_field_missions: true }} />)
    expect(await screen.findByRole("link", { name: "محل النور" })).toHaveAttribute("href", "/field-missions/4/")
  })

  it("shows the mission on its own page, including the governor redirect", async () => {
    mockFetch((url) => {
      if (url === "/api/field-missions/4/") return { status: 200, body: mission }
      if (url.startsWith("/api/users/")) return page([])
      return undefined
    })
    const governor = { ...base, id: 2, role: "governor" as const, governorate: 1, can_open_field_missions: true, can_view_field_missions: true }
    render(
      <MemoryRouter initialEntries={["/field-missions/4/"]}>
        <Routes>
          <Route path="/field-missions/:id/" element={<FieldMissionPage user={governor} />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByRole("heading", { name: "محل النور" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "العودة إلى المهمات الميدانية" })).toHaveAttribute("href", "/field-missions/")
    expect(screen.getByRole("list", { name: "سجل حركة المهمة" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "إعادة التوجيه" })).toBeInTheDocument()
  })
})
