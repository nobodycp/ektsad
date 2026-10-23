import { act, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, vi } from "vitest"
import { App } from "./App"
import type { SessionUser } from "./api"
import { primeSession } from "./auth"

const admin: SessionUser = { id: 1, username: "admin", display_name: "المدير", role: "admin" }

type Reply = { status: number; body: unknown }

function mockFetch(handler: (url: string, init?: RequestInit) => Reply) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const { status, body } = handler(url, init)
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
  })
  vi.stubGlobal("fetch", fn)
  return fn
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

function sidebarLabels() {
  const nav = screen.getByRole("navigation", { name: "التنقل الرئيسي" })
  return within(nav)
    .getAllByRole("link")
    .map((a) => a.textContent)
}

function field(label: string) {
  return screen.getByLabelText(new RegExp(`^${label}\\*?$`), { selector: "input" }) as HTMLInputElement
}

let user: ReturnType<typeof userEvent.setup>

beforeEach(() => {
  user = userEvent.setup()
  primeSession(admin)
  mockFetch(() => ({ status: 403, body: { detail: "Forbidden" } }))
})

afterEach(() => {
  primeSession(undefined)
  vi.unstubAllGlobals()
})

it("moves from complaints to account without a document navigation", async () => {
  render(<MemoryRouter initialEntries={["/complaints/"]}><App /></MemoryRouter>)
  await user.click(screen.getByRole("link", { name: "الإعدادات" }))
  expect(screen.getByRole("heading", { name: "الإعدادات" })).toBeInTheDocument()
})

it("prevents the browser default on sidebar links", async () => {
  renderAt("/complaints/")
  const link = screen.getByRole("link", { name: "الإعدادات" })
  const event = new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 })
  act(() => {
    link.dispatchEvent(event)
  })
  expect(event.defaultPrevented).toBe(true)
  expect(await screen.findByRole("heading", { name: "الإعدادات" })).toBeInTheDocument()
})

it("shows the exact message when login fails", async () => {
  primeSession(null)
  const fetchFn = mockFetch((url) =>
    url === "/api/auth/login/"
      ? { status: 400, body: { detail: "بيانات الدخول غير صحيحة." } }
      : { status: 403, body: { detail: "Forbidden" } },
  )
  renderAt("/")
  await user.type(field("اسم المستخدم"), "someone")
  await user.type(field("كلمة المرور"), "wrong-password")
  await user.click(screen.getByRole("button", { name: "دخول" }))
  expect(await screen.findByRole("alert")).toHaveTextContent(/^بيانات الدخول غير صحيحة\.$/)
  const loginCall = fetchFn.mock.calls.find(([url]) => url === "/api/auth/login/")
  expect(loginCall?.[1]?.method).toBe("POST")
  expect(loginCall?.[1]?.credentials).toBe("include")
  expect(JSON.parse(String(loginCall?.[1]?.body))).toEqual({ username: "someone", password: "wrong-password" })
})

it("signs in and lands on complaints", async () => {
  primeSession(null)
  mockFetch((url) =>
    url === "/api/auth/login/" ? { status: 200, body: admin } : { status: 403, body: { detail: "Forbidden" } },
  )
  renderAt("/")
  await user.type(field("اسم المستخدم"), "admin")
  await user.type(field("كلمة المرور"), "correct-horse-battery")
  await user.click(screen.getByRole("button", { name: "دخول" }))
  expect(await screen.findByRole("heading", { name: "الشكاوى" })).toBeInTheDocument()
})

it("sends anonymous visitors to the login page", async () => {
  primeSession(null)
  renderAt("/account/")
  expect(screen.getByRole("heading", { name: "تسجيل الدخول" })).toBeInTheDocument()
})

it("builds the sidebar for each role", () => {
  const expected: Record<SessionUser["role"], string[]> = {
    admin: ["المحافظات", "المناطق", "المستخدمون", "الشكاوى", "التقارير", "صحة تلغرام", "الأسعار", "المعابر", "الإعدادات"],
    governor: ["الشكاوى", "التقرير اليومي", "الإعدادات"],
    inspector: ["الشكاوى", "الإعدادات"],
    legal: ["الشكاوى", "الإعدادات"],
  }
  for (const role of Object.keys(expected) as SessionUser["role"][]) {
    primeSession({ ...admin, role })
    const { unmount } = renderAt("/complaints/")
    expect(sidebarLabels()).toEqual(expected[role])
    unmount()
  }
})

it("navigates to every sidebar page for admin", async () => {
  renderAt("/complaints/")
  for (const label of ["المحافظات", "المناطق", "المستخدمون", "التقارير", "صحة تلغرام", "الأسعار", "المعابر"]) {
    await user.click(screen.getByRole("link", { name: label }))
    expect(screen.getByRole("heading", { level: 1, name: label })).toBeInTheDocument()
  }
})

it("blocks a route the role cannot use", () => {
  primeSession({ ...admin, role: "inspector" })
  renderAt("/users/")
  expect(screen.getByText("لا تملك صلاحية الوصول إلى هذه الصفحة.")).toBeInTheDocument()
})

it("blocks the governor report for admin", () => {
  renderAt("/governor/report/")
  expect(screen.getByText("لا تملك صلاحية الوصول إلى هذه الصفحة.")).toBeInTheDocument()
})

it("saves the display name with PATCH and the CSRF header", async () => {
  document.cookie = "csrftoken=token-123"
  const fetchFn = mockFetch((url) =>
    url === "/api/users/1/"
      ? { status: 200, body: { id: 1, username: "admin", display_name: "مدير جديد" } }
      : { status: 403, body: {} },
  )
  renderAt("/account/")
  const nameInput = field("الاسم الظاهر")
  await user.clear(nameInput)
  await user.type(nameInput, "مدير جديد")
  await user.click(screen.getByRole("button", { name: "حفظ الاسم" }))
  expect(await screen.findByText("تم حفظ الاسم الظاهر.")).toBeInTheDocument()
  const call = fetchFn.mock.calls.find(([url]) => url === "/api/users/1/")
  expect(call?.[1]?.method).toBe("PATCH")
  expect((call?.[1]?.headers as Record<string, string>)["X-CSRFToken"]).toBe("token-123")
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ display_name: "مدير جديد" })
  document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT"
})

it("requires 12 characters and a matching confirmation before calling the server", async () => {
  const fetchFn = mockFetch(() => ({ status: 403, body: {} }))
  renderAt("/account/")
  await user.type(field("كلمة المرور الحالية"), "old-password-1")
  await user.type(field("كلمة المرور الجديدة"), "short")
  await user.type(field("تأكيد كلمة المرور الجديدة"), "different")
  await user.click(screen.getByRole("button", { name: "تغيير كلمة المرور" }))
  expect(screen.getByText("يجب ألا تقل كلمة المرور الجديدة عن 12 حرفاً.")).toBeInTheDocument()
  expect(screen.getByText("تأكيد كلمة المرور لا يطابق الكلمة الجديدة.")).toBeInTheDocument()
  expect(fetchFn).not.toHaveBeenCalled()
})

it("shows a clear Arabic error when the password endpoint is missing", async () => {
  const fetchFn = mockFetch(() => ({ status: 404, body: { detail: "Not found" } }))
  renderAt("/account/")
  await user.type(field("كلمة المرور الحالية"), "old-password-1")
  await user.type(field("كلمة المرور الجديدة"), "new-password-123")
  await user.type(field("تأكيد كلمة المرور الجديدة"), "new-password-123")
  await user.click(screen.getByRole("button", { name: "تغيير كلمة المرور" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("تغيير كلمة المرور غير متاح على الخادم حالياً.")
  const [url, init] = fetchFn.mock.calls[0]
  expect(url).toBe("/api/users/1/password/")
  expect(init?.method).toBe("POST")
  expect(JSON.parse(String(init?.body))).toEqual({
    mode: "set",
    password: "new-password-123",
    password_confirm: "new-password-123",
    current_password: "old-password-1",
  })
})
