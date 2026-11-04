import { Button } from "../design-system"
import { apiRequest, withQuery, type Page, type Place, type SessionUser } from "../api"
import { Loaded, useLoad } from "./common"

export function listsByGovernorate(user: SessionUser) {
  return user.role === "custom" && Boolean(user.can_view_all_complaints)
}

export function GovernorateSwitch({
  selected,
  onSelect,
}: {
  selected: number | null
  onSelect: (id: number) => void
}) {
  const { state, reload } = useLoad(
    () => apiRequest<Page<Place>>(withQuery("/api/governorates/public/", { page_size: 100 })),
    [],
  )
  return (
    <Loaded state={state} onRetry={reload}>
      {(data) => (
        <div className="ds-govswitch" role="group" aria-label="المحافظات">
          {data.results.map((item) => (
            <Button
              key={item.id}
              size="sm"
              variant={selected === item.id ? "primary" : "secondary"}
              onClick={() => onSelect(item.id)}
            >
              {item.name}
            </Button>
          ))}
        </div>
      )}
    </Loaded>
  )
}
