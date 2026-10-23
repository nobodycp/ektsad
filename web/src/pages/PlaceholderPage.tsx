import { EmptyState } from "../design-system"

export function PlaceholderPage({ label }: { label: string }) {
  return <EmptyState title={`صفحة ${label} قيد الإعداد.`} description="ستتوفر محتويات هذه الصفحة في تحديث قادم." />
}
