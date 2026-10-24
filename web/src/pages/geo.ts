import { useEffect, useState } from "react"
import { apiRequest, withQuery, type Page, type Place, type RegionPlace } from "../api"
import { ALL_ROWS } from "./common"

export type Geography = { governorates: Place[]; regions: RegionPlace[] }

/** Admin geography lists for selects and name lookups. `version` refetches after a create. */
export function useAdminGeography(version = 0): Geography {
  const [geo, setGeo] = useState<Geography>({ governorates: [], regions: [] })
  useEffect(() => {
    let cancelled = false
    const load = async <T,>(staffPath: string, publicPath: string) => {
      const staff = await apiRequest<Page<T>>(withQuery(staffPath, { page_size: ALL_ROWS }))
      if (staff.ok && staff.data) return staff.data.results
      const open = await apiRequest<Page<T>>(withQuery(publicPath, { page_size: ALL_ROWS }))
      return open.data?.results ?? []
    }
    Promise.all([
      load<Place>("/api/governorates/", "/api/governorates/public/"),
      load<RegionPlace>("/api/regions/", "/api/regions/public/"),
    ]).then(([governorates, regions]) => {
      if (cancelled) return
      setGeo({ governorates, regions })
    })
    return () => {
      cancelled = true
    }
  }, [version])
  return geo
}

export function nameOf(items: Place[], id: number | null | undefined): string {
  if (id == null) return "—"
  return items.find((item) => item.id === id)?.name ?? String(id)
}

export const optionsOf = (items: Place[]) => items.map((item) => ({ value: String(item.id), label: item.name }))
