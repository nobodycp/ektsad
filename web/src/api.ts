export type Role = "admin" | "governor" | "inspector" | "legal"

export type SessionUser = {
  id: number
  username: string
  display_name: string
  role: Role
  governorate: number | null
  governorate_name: string | null
  region: number | null
  region_name: string | null
  can_publish_prices: boolean
  can_publish_crossings: boolean
  can_view_all_complaints: boolean
}

export type PublishFlag = "can_publish_prices" | "can_publish_crossings"

export type ApiResult<T = unknown> = { ok: boolean; status: number; data: T | null }

export type Page<T> = { count: number; page: number; page_size: number; results: T[] }

export type Place = { id: number; name: string }
export type RegionPlace = Place & { governorate: number }

export type ComplaintRow = {
  id: number
  governorate: number
  governorate_name: string
  region: number
  region_name: string
  title: string
  body: string
  status: string
  inspector: number | null
  inspector_name: string
  created_at: string
  is_flagged: boolean
  source?: string
  submitter_ip?: string | null
  telegram_user_id?: string
  has_image?: boolean
  field_replied_at?: string | null
  accepted_at?: string | null
  legal_referred_at?: string | null
  closed_at?: string | null
  assigned_by_name?: string
}

export type FollowUpLine = {
  id: number
  author_name: string
  created_at: string
  place: "field" | "legal" | string
  body: string
  files: { id: number; name: string }[]
}

export type ComplaintDetail = ComplaintRow & { follow_ups: FollowUpLine[] }

export type UserRow = {
  id: number
  username: string
  display_name: string
  role: Role
  governorate: number | null
  region: number | null
  can_publish_prices: boolean
  can_publish_crossings: boolean
  can_view_all_complaints: boolean
  is_active: boolean
}

export type ActionResult = { succeeded: number[]; failed: { id: number; detail: string }[] }

export type Publication = { id: number; published_at: string; publisher_name: string; has_image: boolean; body?: string }

type Method = "GET" | "POST" | "PATCH" | "DELETE"

export function readCookie(name: string): string | null {
  const prefix = `${name}=`
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) return decodeURIComponent(trimmed.slice(prefix.length))
  }
  return null
}

async function send<T>(path: string, method: Method, headers: Record<string, string>, body?: BodyInit): Promise<ApiResult<T>> {
  const allHeaders: Record<string, string> = { Accept: "application/json", ...headers }
  if (method !== "GET") {
    const token = readCookie("csrftoken")
    if (token) allHeaders["X-CSRFToken"] = token
  }
  let response: Response
  try {
    response = await fetch(path, { method, headers: allHeaders, credentials: "include", body })
  } catch {
    return { ok: false, status: 0, data: null }
  }
  let data: T | null = null
  try {
    data = (await response.json()) as T
  } catch {
    data = null
  }
  return { ok: response.ok, status: response.status, data }
}

export function apiRequest<T = unknown>(
  path: string,
  options: { method?: Method; body?: unknown } = {},
): Promise<ApiResult<T>> {
  const hasBody = options.body !== undefined
  return send<T>(
    path,
    options.method ?? "GET",
    hasBody ? { "Content-Type": "application/json" } : {},
    hasBody ? JSON.stringify(options.body) : undefined,
  )
}

/** The browser must set the multipart boundary, so no Content-Type header is sent here. */
export function apiUpload<T = unknown>(path: string, form: FormData, method: "POST" | "PATCH" = "POST") {
  return send<T>(path, method, {}, form)
}

export function withQuery(path: string, params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value))
  }
  const text = query.toString()
  return text ? `${path}?${text}` : path
}

export function errorDetail(data: unknown): string | null {
  if (!data || typeof data !== "object") return null
  const record = data as Record<string, unknown>
  if (typeof record.detail === "string") return record.detail
  for (const value of Object.values(record)) {
    if (typeof value === "string") return value
    if (Array.isArray(value) && typeof value[0] === "string") return value[0]
  }
  return null
}

export const fetchMe = () => apiRequest<SessionUser>("/api/auth/me/")

export async function ensureCsrfCookie() {
  if (!readCookie("csrftoken")) await fetchMe()
}

export const postLogin = (username: string, password: string) =>
  apiRequest<SessionUser>("/api/auth/login/", { method: "POST", body: { username, password } })

export const postLogout = () => apiRequest("/api/auth/logout/", { method: "POST" })

export const patchDisplayName = (id: number, display_name: string) =>
  apiRequest<Pick<SessionUser, "id" | "username" | "display_name">>(`/api/users/${id}/`, {
    method: "PATCH",
    body: { display_name },
  })

export const postPasswordChange = (
  id: number,
  body: { password: string; password_confirm: string; current_password: string },
) => apiRequest(`/api/users/${id}/password/`, { method: "POST", body: { mode: "set", ...body } })

export const postComplaintAction = (action: "accept" | "flag" | "unflag", ids: number[]) =>
  apiRequest<ActionResult>("/api/complaints/actions/", { method: "POST", body: { action, ids } })
