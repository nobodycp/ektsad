import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { fetchMe, postLogout, type SessionUser } from "./api"

type SessionState = { status: "loading" } | { status: "anonymous" } | { status: "signed_in"; user: SessionUser }

let cachedSession: SessionUser | null | undefined

export function primeSession(user: SessionUser | null | undefined) {
  cachedSession = user
}

function initialState(): SessionState {
  if (cachedSession === undefined) return { status: "loading" }
  return cachedSession ? { status: "signed_in", user: cachedSession } : { status: "anonymous" }
}

type AuthValue = {
  session: SessionState
  signIn: (user: SessionUser) => void
  updateUser: (patch: Partial<SessionUser>) => void
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionState>(initialState)

  useEffect(() => {
    if (cachedSession !== undefined) return
    let cancelled = false
    fetchMe().then((result) => {
      if (cancelled) return
      const user = result.ok && result.data ? result.data : null
      cachedSession = user
      setSession(user ? { status: "signed_in", user } : { status: "anonymous" })
    })
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback((user: SessionUser) => {
    cachedSession = user
    setSession({ status: "signed_in", user })
  }, [])

  const updateUser = useCallback((patch: Partial<SessionUser>) => {
    setSession((current) => {
      if (current.status !== "signed_in") return current
      const user = { ...current.user, ...patch }
      cachedSession = user
      return { status: "signed_in", user }
    })
  }, [])

  const signOut = useCallback(async () => {
    await postLogout()
    cachedSession = null
    setSession({ status: "anonymous" })
  }, [])

  const value = useMemo(() => ({ session, signIn, updateUser, signOut }), [session, signIn, updateUser, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside AuthProvider")
  return value
}

export function useAuthOptional(): AuthValue | null {
  return useContext(AuthContext)
}
