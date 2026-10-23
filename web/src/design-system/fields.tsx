import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react"

type FieldFrameProps = {
  id: string
  label: string
  hint?: string
  error?: string
  required?: boolean
  type?: string
  children: ReactNode
}

function FieldFrame({ id, label, hint, error, required, type, children }: FieldFrameProps) {
  return (
    <div className="ds-field" data-type={type}>
      <label className="ds-field__label" htmlFor={id}>
        {label}
        {required && (
          <span className="ds-field__required" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children}
      {hint && !error && (
        <span className="ds-field__hint" id={`${id}-hint`}>
          {hint}
        </span>
      )}
      {error && (
        <span className="ds-field__error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </div>
  )
}

type CommonProps = { label: string; hint?: string; error?: string }

function useFieldIds(explicitId: string | undefined, hint?: string, error?: string) {
  const generated = useId()
  const id = explicitId ?? generated
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return { id, describedBy }
}

export type TextFieldProps = CommonProps & Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  type?: "text" | "search" | "email" | "tel" | "number" | "password" | "date"
}

export function TextField({ label, hint, error, id: explicitId, type = "text", required, ...rest }: TextFieldProps) {
  const { id, describedBy } = useFieldIds(explicitId, hint, error)
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error} required={required} type={type}>
      <input
        {...rest}
        id={id}
        type={type}
        required={required}
        className="ds-field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
    </FieldFrame>
  )
}

export type SelectOption = { value: string; label: string }

export type SelectProps = CommonProps & SelectHTMLAttributes<HTMLSelectElement> & {
  options: SelectOption[]
  placeholder?: string
}

export function Select({ label, hint, error, id: explicitId, options, placeholder, required, ...rest }: SelectProps) {
  const { id, describedBy } = useFieldIds(explicitId, hint, error)
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error} required={required} type="select">
      <select
        {...rest}
        id={id}
        required={required}
        className="ds-field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      >
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldFrame>
  )
}

export type TextAreaProps = CommonProps & TextareaHTMLAttributes<HTMLTextAreaElement>

export function TextArea({ label, hint, error, id: explicitId, required, ...rest }: TextAreaProps) {
  const { id, describedBy } = useFieldIds(explicitId, hint, error)
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error} required={required} type="textarea">
      <textarea
        {...rest}
        id={id}
        required={required}
        className="ds-field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
    </FieldFrame>
  )
}

export type FileFieldProps = CommonProps & Omit<InputHTMLAttributes<HTMLInputElement>, "type">

export function FileField({ label, hint, error, id: explicitId, required, ...rest }: FileFieldProps) {
  const { id, describedBy } = useFieldIds(explicitId, hint, error)
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error} required={required} type="file">
      <input
        {...rest}
        id={id}
        type="file"
        required={required}
        className="ds-field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
    </FieldFrame>
  )
}
