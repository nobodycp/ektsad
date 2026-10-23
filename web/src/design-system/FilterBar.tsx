import { useState } from "react"
import { Button } from "./Button"
import { Select, TextField, type SelectOption } from "./fields"

export const FILTER_QUERY_KEYS = [
  "q",
  "status",
  "governorate",
  "region",
  "inspector",
  "date_from",
  "date_to",
  "role",
  "is_active",
] as const

export type FilterQueryKey = (typeof FILTER_QUERY_KEYS)[number]
export type FilterValues = Partial<Record<FilterQueryKey, string>>

export type FilterField =
  | { type: "search"; key: "q"; label: string; placeholder?: string }
  | {
      type: "select"
      key: Exclude<FilterQueryKey, "q" | "date_from" | "date_to">
      label: string
      options: SelectOption[]
      placeholder?: string
    }
  | { type: "date"; key: "date_from" | "date_to"; label: string }
  | { type: "date_range"; key: string; label: string; fromLabel?: string; toLabel?: string }

export type FilterBarProps = {
  schema: FilterField[]
  onChange: (values: FilterValues) => void
  initialValues?: FilterValues
}

function compact(values: FilterValues): FilterValues {
  const out: FilterValues = {}
  for (const key of FILTER_QUERY_KEYS) {
    const v = values[key]
    if (v !== undefined && v !== "") out[key] = v
  }
  return out
}

export function FilterBar({ schema, onChange, initialValues = {} }: FilterBarProps) {
  const [values, setValues] = useState<FilterValues>(() => compact(initialValues))

  const update = (key: FilterQueryKey, value: string) => {
    const next = compact({ ...values, [key]: value })
    setValues(next)
    onChange(next)
  }

  const reset = () => {
    setValues({})
    onChange({})
  }

  return (
    <div className="ds-filterbar" role="search" aria-label="تصفية النتائج">
      {schema.map((field) => {
        switch (field.type) {
          case "search":
            return (
              <TextField
                key={field.key}
                type="search"
                label={field.label}
                placeholder={field.placeholder}
                value={values.q ?? ""}
                onChange={(e) => update("q", e.target.value)}
              />
            )
          case "select":
            return (
              <Select
                key={field.key}
                label={field.label}
                options={field.options}
                placeholder={field.placeholder ?? "الكل"}
                value={values[field.key] ?? ""}
                onChange={(e) => update(field.key, e.target.value)}
              />
            )
          case "date":
            return (
              <TextField
                key={field.key}
                type="date"
                label={field.label}
                value={values[field.key] ?? ""}
                onChange={(e) => update(field.key, e.target.value)}
              />
            )
          case "date_range":
            return (
              <fieldset key={field.key} className="ds-filterbar__range" style={{ border: 0, margin: 0, padding: 0 }}>
                <legend className="ds-visually-hidden">{field.label}</legend>
                <TextField
                  type="date"
                  label={field.fromLabel ?? "من تاريخ"}
                  value={values.date_from ?? ""}
                  onChange={(e) => update("date_from", e.target.value)}
                />
                <TextField
                  type="date"
                  label={field.toLabel ?? "إلى تاريخ"}
                  value={values.date_to ?? ""}
                  onChange={(e) => update("date_to", e.target.value)}
                />
              </fieldset>
            )
        }
      })}
      <div className="ds-filterbar__actions">
        <Button variant="ghost" onClick={reset}>
          مسح الفلاتر
        </Button>
      </div>
    </div>
  )
}
