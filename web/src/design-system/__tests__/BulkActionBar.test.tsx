import { render, screen } from "@testing-library/react"
import { BulkActionBar } from "../index"

describe("BulkActionBar", () => {
  it("renders nothing when there are no bulk actions", () => {
    const { container } = render(<BulkActionBar actions={[]} selectedIds={[1, 2]} onClear={() => {}} />)
    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByTestId("bulk-action-bar")).not.toBeInTheDocument()
  })

  it("renders nothing when nothing is selected", () => {
    const { container } = render(
      <BulkActionBar actions={[{ id: "a", label: "إجراء", onRun: () => {} }]} selectedIds={[]} onClear={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
