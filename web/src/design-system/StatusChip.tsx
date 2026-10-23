export const STATUS_LABELS = [
  "واردة",
  "قيد المتابعة الميدانية",
  "منتهية",
  "قيد المتابعة في الشؤون القانونية",
  "تم المعالجه خلص",
] as const

export type StatusLabel = (typeof STATUS_LABELS)[number]

const TONES: Record<StatusLabel, string> = {
  "واردة": "incoming",
  "قيد المتابعة الميدانية": "field",
  "منتهية": "closed",
  "قيد المتابعة في الشؤون القانونية": "legal",
  "تم المعالجه خلص": "resolved",
}

export function StatusChip({ status }: { status: StatusLabel | string }) {
  const tone = TONES[status as StatusLabel] ?? "unknown"
  return (
    <span className="ds-chip" data-tone={tone}>
      {status}
    </span>
  )
}
