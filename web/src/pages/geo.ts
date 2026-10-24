import { useEffect, useState } from "react"
import { apiRequest, withQuery, type Page, type Place, type RegionPlace } from "../api"
import { ALL_ROWS } from "./common"

export type Geography = { governorates: Place[]; regions: RegionPlace[] }

/** Admin geography lists for selects and name lookups. `version` refetches after a create. */
export function useAdminGeography(version = 0): Geography {
  const [geo, setGeo] = useState<Geography>({ governorates: [], regions: [] })
  useEffect(() => {
    let cancelled = false
    Promise.all([
      apiRequest<Page<Place>>(withQuery("/api/governorates/", { page_size: ALL_ROWS })),
      apiRequest<Page<RegionPlace>>(withQuery("/api/regions/", { page_size: ALL_ROWS })),
    ]).then(([governorates, regions]) => {
      if (cancelled) return
      setGeo({ governorates: governorates.data?.results ?? [], regions: regions.data?.results ?? [] })
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
