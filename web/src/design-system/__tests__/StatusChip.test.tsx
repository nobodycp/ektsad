import { render, screen } from "@testing-library/react"
import { StatusChip, STATUS_LABELS } from "../index"

describe("StatusChip", () => {
  it("renders the five status labels from one chip", () => {
    for (const label of ["واردة", "قيد المتابعة الميدانية", "منتهية", "قيد المتابعة في الشؤون القانونية", "تم المعالجه خلص"]) {
      render(<StatusChip status={label} />)
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it("exposes exactly the five known labels", () => {
    expect(STATUS_LABELS).toEqual([
      "واردة",
      "قيد المتابعة الميدانية",
      "منتهية",
      "قيد المتابعة في الشؤون القانونية",
      "تم المعالجه خلص",
    ])
  })

  it("assigns a distinct tone per status", () => {
    const tones = STATUS_LABELS.map((label) => {
      const { container, unmount } = render(<StatusChip status={label} />)
      const tone = (container.firstChild as HTMLElement).dataset.tone
      unmount()
      return tone
    })
    expect(new Set(tones).size).toBe(5)
  })
})
