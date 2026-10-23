export type Role = "admin" | "governor" | "inspector" | "legal"

export type SessionUser = {
  id: number
  username: string
  display_name: string
  role: Role
}

export type ApiResult<T = unknown> = { ok: boolean; status: number; data: T | null }

export function readCookie(name: string): string | null {
  const prefix = `${name}=`
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) return decodeURIComponent(trimmed.slice(prefix.length))
  }
  return null
}

export async function apiRequest<T = unknown>(
  path: string,
  options: { method?: "GET" | "POST" | "PATCH"; body?: unknown } = {},
): Promise<ApiResult<T>> {
  const method = options.method ?? "GET"
  const headers: Record<string, string> = { Accept: "application/json" }
  if (options.body !== undefined) headers["Content-Type"] = "application/json"
  if (method !== "GET") {
    const token = readCookie("csrftoken")
    if (token) headers["X-CSRFToken"] = token
  }
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers,
      credentials: "include",
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })
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
