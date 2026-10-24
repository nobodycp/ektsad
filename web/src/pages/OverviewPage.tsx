import { useEffect, useState, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { BarChart, Select, Sparkline, StatusChip, TextField, TrendChart } from "../design-system"
import { apiRequest, withQuery, type Page, type Place, type RegionPlace, type SessionUser } from "../api"
import { navForUser } from "../routes"
import { ALL_ROWS, Loaded, Section, useLoad } from "./common"

type TrendPoint = { date: string; created: number; done: number }

type Overview = {
  period: { from: string; to: string; previous_from: string; previous_to: string }
  current: {
    total: number
    done: number
    remaining: number
    percent_done: number | null
    by_status: Record<string, number>
  }
  period_metrics: {
    created: number
    created_previous: number
    created_delta: number
    created_percent: number | null
    done: number
    done_previous: number
    done_delta: number
    done_percent: number | null
    pending_at_end: number
    pending_previous: number
    pending_delta: number
    pending_percent: number | null
    legal_referred: number
    legal_resolved: number
    still_legal: number
  }
  trend: TrendPoint[] | null
  trend_note: string | null
  attention: ({ kind: "status"; status: string; count: number } | { kind: "flagged"; count: number })[]
  inspectors: { id: number; name: string; done: number }[] | null
  publications: { prices?: number; crossings?: number } | null
  recent: { id: number; title: string; status: string; region_name: string; created_at: string }[]
}

const STATUS_ORDER = ["واردة", "قيد المتابعة الميدانية", "منتهية", "قيد المتابعة في الشؤون القانونية", "تم المعالجه خلص"]

function signed(value: number) {
  if (value > 0) return `+${value}`
  return String(value)
}

function Delta({
  delta,
  percent,
  tone,
}: {
  delta: number
  percent: number | null
  tone: "neutral" | "good" | "warn"
}) {
  const direction = delta > 0 ? "up" : delta < 0 ? "down" : "flat"
  const text = percent === null ? signed(delta) : `${signed(percent)}%`
  return (
    <span className={`ov-delta ov-delta--${tone} ov-delta--${direction}`} dir="ltr">
      {text}
    </span>
  )
}

function Stat({
  label,
  value,
  meta,
  href,
  delta,
  spark,
  tone,
}: {
  label: string
  value: number
  meta: string
  href?: string
  delta?: ReactNode
  spark?: number[]
  tone?: "ink" | "success"
}) {
  const body = (
    <>
      <span className="ov-stat__head">
        <span className="ov-stat__label">{label}</span>
        {delta}
      </span>
      <span className="ov-stat__figure">
        <strong className="ov-stat__value">{value}</strong>
        {spark && <Sparkline values={spark} tone={tone} />}
      </span>
      <span className="ov-stat__meta">{meta}</span>
    </>
  )
  if (href) {
    return (
      <Link className="ov-stat" to={href}>
        {body}
      </Link>
    )
  }
  return <article className="ov-stat">{body}</article>
}

function compareMeta(previous: number, percent: number | null) {
  if (previous === 0 && percent === null) return "الفترة السابقة كانت صفراً، بلا نسبة"
  return "مقابل الفترة السابقة"
}

export function OverviewPage({ user }: { user: SessionUser }) {
  const [from, setFrom] = useState("")
  const [to, setTo] = useState("")
  const [governorate, setGovernorate] = useState("")
  const [region, setRegion] = useState("")
  const [governorates, setGovernorates] = useState<Place[]>([])
  const [regions, setRegions] = useState<RegionPlace[]>([])
  const canScope = user.role === "admin" || user.role === "governor"

  useEffect(() => {
    if (!canScope) return
    let cancelled = false
    const path = user.role === "admin" ? "/api/governorates/" : "/api/governorates/public/"
    if (user.role === "admin") {
      apiRequest<Page<Place>>(withQuery(path, { page_size: ALL_ROWS })).then((result) => {
        if (!cancelled && result.ok && result.data) setGovernorates(result.data.results)
      })
    }
    return () => {
      cancelled = true
    }
  }, [canScope, user.role])

  useEffect(() => {
    if (!canScope) return
    let cancelled = false
    const governorateId = user.role === "governor" ? user.governorate : governorate
    if (!governorateId) {
      setRegions([])
      return
    }
    const query = governorateId ? { governorate: governorateId, page_size: ALL_ROWS } : { page_size: ALL_ROWS }
    const path = user.role === "admin" ? "/api/regions/" : "/api/regions/public/"
    apiRequest<Page<RegionPlace>>(withQuery(path, query)).then((result) => {
      if (!cancelled && result.ok && result.data) setRegions(result.data.results)
    })
    return () => {
      cancelled = true
    }
  }, [canScope, governorate, user.governorate, user.role])

  const { state, reload } = useLoad(
    () =>
      apiRequest<Overview>(
        withQuery("/api/reports/overview/", {
          date_from: from,
          date_to: to,
          governorate: user.role === "admin" ? governorate : undefined,
          region: canScope ? region : undefined,
        }),
      ),
    [from, to, governorate, region, canScope, user.role],
  )

  const shortcuts = navForUser(user).filter((route) => route.id !== "overview").slice(0, 4)

  return (
    <div className="ov">
      <div className="ov-filters">
        <TextField label="من" type="date" name="date_from" value={from} onChange={(event) => setFrom(event.target.value)} />
        <TextField label="إلى" type="date" name="date_to" value={to} onChange={(event) => setTo(event.target.value)} />
        {user.role === "admin" && (
          <Select
            label="المحافظة"
            name="governorate"
            placeholder="كل المحافظات"
            options={governorates.map((item) => ({ value: String(item.id), label: item.name }))}
            value={governorate}
            onChange={(event) => {
              setGovernorate(event.target.value)
              setRegion("")
            }}
          />
        )}
        {canScope && (
          <Select
            label="المنطقة"
            name="region"
            placeholder="كل المناطق"
            options={regions.map((item) => ({ value: String(item.id), label: item.name }))}
            value={region}
            onChange={(event) => setRegion(event.target.value)}
          />
        )}
      </div>
      <Loaded state={state} onRetry={reload}>
        {(data) => {
          const period = data.period_metrics
          const sparkCreated = data.trend?.map((point) => point.created)
          const sparkDone = data.trend?.map((point) => point.done)
          const statusRows = STATUS_ORDER.map((status) => ({ status, value: data.current.by_status[status] ?? 0 }))
          const statusTotal = statusRows.reduce((sum, row) => sum + row.value, 0)
          const range = `${data.period.from} → ${data.period.to}`
          return (
            <>
              <p className="ov-range">
                الفترة {range}. المجاميع الحالية لا تتأثر بها. المقارنة مع {data.period.previous_from} → {data.period.previous_to}.
              </p>
              <div className="ov-kpis">
                <Stat
                  label="الشكاوى الآن"
                  value={data.current.total}
                  meta="وضع حالي"
                  href="/complaints/"
                />
                <Stat
                  label="جديدة في الفترة"
                  value={period.created}
                  meta={compareMeta(period.created_previous, period.created_percent)}
                  delta={<Delta delta={period.created_delta} percent={period.created_percent} tone="neutral" />}
                  spark={sparkCreated}
                  href={`/complaints/?created_from=${data.period.from}&created_to=${data.period.to}`}
                />
                <Stat
                  label="منجز الفترة"
                  value={period.done}
                  meta={compareMeta(period.done_previous, period.done_percent)}
                  delta={<Delta delta={period.done_delta} percent={period.done_percent} tone="good" />}
                  spark={sparkDone}
                  tone="success"
                  href={`/complaints/?closed_from=${data.period.from}&closed_to=${data.period.to}`}
                />
                <Stat
                  label="معلق حتى نهاية الفترة"
                  value={period.pending_at_end}
                  meta={`${compareMeta(period.pending_previous, period.pending_percent)}. مقبول ولم يُغلق.`}
                  delta={<Delta delta={period.pending_delta} percent={period.pending_percent} tone="warn" />}
                />
              </div>

              <section className="ov-card" aria-label="تقدم المعالجة">
                <header className="ov-card__head">
                  <h2>تقدم المعالجة</h2>
                  <span>وضع حالي</span>
                </header>
                {data.current.total === 0 ? (
                  <p className="ov-empty">لا شكاوى في هذا النطاق.</p>
                ) : (
                  <>
                    <div
                      className="ov-progress"
                      role="img"
                      aria-label={`${data.current.done} منجزة من ${data.current.total}، ${data.current.percent_done} بالمئة`}
                    >
                      <span style={{ width: `${data.current.percent_done ?? 0}%` }} />
                    </div>
                    <p className="ov-progress__caption">
                      <strong>{data.current.percent_done}%</strong>
                      <span>
                        {data.current.done} منجزة · {data.current.remaining} متبقية
                      </span>
                    </p>
                  </>
                )}
              </section>

              <div className="ov-split">
                <Section title="حركة الفترة" note={data.trend_note || "جديدة ومنجزة لكل يوم. الأقدم يميناً."}>
                  {data.trend && data.trend.length >= 2 ? (
                    <TrendChart
                      label={`من ${data.period.from} إلى ${data.period.to}: ${period.created} شكوى جديدة و${period.done} منجزة.`}
                      points={data.trend}
                    />
                  ) : (
                    <p className="ov-empty">{data.trend_note || "اليوم الواحد لا يرسم خطاً. العددان في البطاقات أعلاه."}</p>
                  )}
                  <ul className="ov-legend">
                    <li><i className="ov-swatch ov-swatch--ink" /> جديدة</li>
                    <li><i className="ov-swatch ov-swatch--done" /> منجزة</li>
                  </ul>
                </Section>
                <Section title="الحالات الآن" note="توزيع الوضع الحالي، وليس الفترة.">
                  {statusTotal === 0 ? (
                    <p className="ov-empty">لا شكاوى.</p>
                  ) : (
                    <div className="ov-stack" role="img" aria-label={statusRows.map((row) => `${row.status} ${row.value}`).join("، ")}>
                      {statusRows
                        .filter((row) => row.value > 0)
                        .map((row) => (
                          <Link
                            key={row.status}
                            className={`ov-stack__seg ov-stack__seg--${row.status === "واردة" ? "incoming" : row.status === "قيد المتابعة الميدانية" ? "field" : row.status === "منتهية" ? "closed" : row.status === "قيد المتابعة في الشؤون القانونية" ? "legal" : "resolved"}`}
                            style={{ width: `${(row.value / statusTotal) * 100}%` }}
                            to={`/complaints/?status=${encodeURIComponent(row.status)}`}
                            title={`${row.status}: ${row.value}`}
                          />
                        ))}
                    </div>
                  )}
                  <ul className="ov-status">
                    {statusRows.map((row) => (
                      <li key={row.status}>
                        <Link to={`/complaints/?status=${encodeURIComponent(row.status)}`}>
                          <StatusChip status={row.status} />
                          <strong>{row.value}</strong>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </Section>
              </div>

              <div className="ov-split">
                <Section title="يحتاج إجراء" note="من الوضع الحالي.">
                  {data.attention.length === 0 ? (
                    <p className="ov-empty">لا يوجد ما يحتاج إجراءً.</p>
                  ) : (
                    <ul className="ov-attention">
                      {data.attention.map((item) =>
                        item.kind === "flagged" ? (
                          <li key="flagged">
                            <Link to="/complaints/?flagged=1">
                              <span>معلّمة للمتابعة</span>
                              <strong>{item.count}</strong>
                            </Link>
                          </li>
                        ) : (
                          <li key={item.status}>
                            <Link to={`/complaints/?status=${encodeURIComponent(item.status)}`}>
                              <StatusChip status={item.status} />
                              <strong>{item.count}</strong>
                            </Link>
                          </li>
                        ),
                      )}
                    </ul>
                  )}
                </Section>
                <Section title="الشؤون القانونية في الفترة" note="المحوّل والمنجز خلال الفترة. «ما زال» حتى نهاية الفترة.">
                  <dl className="ov-mini">
                    <div>
                      <dt>محوّل</dt>
                      <dd>{period.legal_referred}</dd>
                    </div>
                    <div>
                      <dt>أُنجز</dt>
                      <dd>{period.legal_resolved}</dd>
                    </div>
                    <div>
                      <dt>ما زال</dt>
                      <dd>{period.still_legal}</dd>
                    </div>
                  </dl>
                </Section>
              </div>

              {data.inspectors && (
                <Section title="منجز المفتشين في الفترة" note="إغلاق بحالة منتهية أو تم المعالجه خلص.">
                  {data.inspectors.length === 0 ? (
                    <p className="ov-empty">لا مفتشون في هذا النطاق.</p>
                  ) : (
                    <BarChart
                      label="منجز كل مفتش في الفترة"
                      rows={data.inspectors.map((person) => ({ key: String(person.id), label: person.name, value: person.done }))}
                    />
                  )}
                </Section>
              )}

              {data.publications && (
                <Section title="النشر في الفترة" note="على مستوى النظام، بلا نطاق جغرافي.">
                  <dl className="ov-mini">
                    {data.publications.prices !== undefined && (
                      <div>
                        <dt>قوائم الأسعار</dt>
                        <dd>{data.publications.prices}</dd>
                      </div>
                    )}
                    {data.publications.crossings !== undefined && (
                      <div>
                        <dt>حركة المعابر</dt>
                        <dd>{data.publications.crossings}</dd>
                      </div>
                    )}
                  </dl>
                </Section>
              )}

              <div className="ov-split">
                <Section title="آخر الشكاوى" note="الأحدث في النطاق، بلا صلة بالفترة.">
                  {data.recent.length === 0 ? (
                    <p className="ov-empty">لا شكاوى.</p>
                  ) : (
                    <ul className="ov-recent">
                      {data.recent.map((row) => (
                        <li key={row.id}>
                          <Link to={`/complaints/${row.id}/`}>
                            <span>{row.title}</span>
                            <small>
                              {row.region_name} · {row.created_at.slice(0, 10)}
                            </small>
                          </Link>
                          <StatusChip status={row.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>
                <Section title="اختصارات">
                  <ul className="ov-links">
                    {shortcuts.map((route) => (
                      <li key={route.id}>
                        <Link to={route.path}>{route.label}</Link>
                      </li>
                    ))}
                  </ul>
                </Section>
              </div>
            </>
          )
        }}
      </Loaded>
    </div>
  )
}
