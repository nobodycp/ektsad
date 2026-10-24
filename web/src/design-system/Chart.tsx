function chartX(index: number, count: number, width: number) {
  if (count <= 1) return width
  return width - (index / (count - 1)) * width
}

export function Sparkline({ values, tone = "ink" }: { values: number[]; tone?: "ink" | "success" }) {
  if (values.length < 2 || values.every((value) => value === 0)) return null
  const max = Math.max(...values)
  const width = 100
  const height = 24
  const points = values
    .map((value, index) => {
      const x = chartX(index, values.length, width)
      const y = height - (value / max) * (height - 2) - 1
      return `${x},${y}`
    })
    .join(" ")
  return (
    <svg className={`ov-spark ov-spark--${tone}`} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={points} />
    </svg>
  )
}

export function TrendChart({
  label,
  points,
}: {
  label: string
  points: { date: string; created: number; done: number }[]
}) {
  if (points.length < 2) return null
  const width = 320
  const height = 120
  const max = Math.max(1, ...points.flatMap((point) => [point.created, point.done]))
  const line = (key: "created" | "done") =>
    points
      .map((point, index) => {
        const x = chartX(index, points.length, width)
        const y = height - 8 - (point[key] / max) * (height - 16)
        return `${x},${y}`
      })
      .join(" ")
  return (
    <div className="ov-trend">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
        <polyline className="ov-trend__created" points={line("created")} />
        <polyline className="ov-trend__done" points={line("done")} />
        {points.map((point, index) => {
          const x = chartX(index, points.length, width)
          return (
            <g key={point.date}>
              <circle cx={x} cy={height - 8 - (point.created / max) * (height - 16)} r="2.5" className="ov-trend__created">
                <title>{`${point.date}: ${point.created} جديدة، ${point.done} منجزة`}</title>
              </circle>
            </g>
          )
        })}
      </svg>
      <div className="ov-trend__axis">
        <span>{points[0].date}</span>
        <span>{points[points.length - 1].date}</span>
      </div>
    </div>
  )
}

export function BarChart({
  label,
  rows,
}: {
  label: string
  rows: { key: string; label: string; value: number }[]
}) {
  const max = Math.max(1, ...rows.map((row) => row.value))
  return (
    <div className="ds-bars" role="img" aria-label={label}>
      {rows.map((row) => (
        <div key={row.key} className="ds-bars__row">
          <span className="ds-bars__label">{row.label}</span>
          <span className="ds-bars__track">
            <span className="ds-bars__fill" style={{ width: `${Math.round((row.value / max) * 100)}%` }} />
          </span>
          <strong className="ds-bars__value">{row.value}</strong>
        </div>
      ))}
    </div>
  )
}
