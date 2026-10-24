import { apiRequest } from "../api"
import { Ledger, Loaded, Section, formatDateTime, useLoad } from "./common"

type Health = {
  registered: boolean
  last_error: string
  last_update_at: string | null
  pending_count: number
  oldest_wait: string | null
}

export function TelegramHealthPage() {
  const { state, reload } = useLoad(() => apiRequest<Health>("/api/telegram/health/"), [])
  return (
    <Loaded state={state} onRetry={reload}>
      {(health) => <HealthView health={health} />}
    </Loaded>
  )
}

function HealthView({ health }: { health: Health }) {
  return (
    <div className="page">
      <Section title="تسجيل الويب هوك" note="فشل التسجيل لا يوقف الموقع. الرسائل تبقى في الصف حتى تنجح.">
        <Ledger
          label="حالة تلغرام"
          figures={[
            { key: "registered", label: "التسجيل", value: health.registered ? "مسجّل" : "غير مسجّل" },
            { key: "error", label: "آخر خطأ", value: health.last_error || "—" },
            { key: "update", label: "آخر تحديث", value: formatDateTime(health.last_update_at) },
            { key: "pending", label: "بانتظار الإرسال", value: health.pending_count },
            { key: "oldest", label: "أقدم انتظار", value: formatDateTime(health.oldest_wait) },
          ]}
        />
      </Section>
    </div>
  )
}
