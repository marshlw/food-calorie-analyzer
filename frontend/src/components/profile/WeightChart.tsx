import React, { useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { TrendingDown, Plus, X } from 'lucide-react'
import { WeightRecord, BodyMetric, BODY_METRICS, BodyMetricMeta } from '../../types'

type Range = 30 | 90 | 365 | 0 // дни, 0 = всё время

const RANGES: { label: string; value: Range }[] = [
  { label: '1М', value: 30 },
  { label: '3М', value: 90 },
  { label: '1Г', value: 365 },
  { label: 'Всё', value: 0 },
]

const meta = (key: BodyMetric): BodyMetricMeta =>
  BODY_METRICS.find((m) => m.key === key) as BodyMetricMeta

interface Props {
  data: WeightRecord[]
}

export const WeightChart: React.FC<Props> = ({ data }) => {
  const [range, setRange] = useState<Range>(90)
  // Основная метрика графика и опциональная вторая для сравнения.
  const [primary, setPrimary] = useState<BodyMetric>('weight_kg')
  const [secondary, setSecondary] = useState<BodyMetric | null>(null)

  // Какие метрики реально заполнены хотя бы в одной записи — только их
  // показываем в переключателе, чтобы не плодить пустые линии.
  const available = useMemo(() => {
    return BODY_METRICS.filter((m) =>
      data.some((r) => r[m.key] != null && !isNaN(Number(r[m.key])))
    )
  }, [data])

  const primaryMeta = meta(primary)
  const secondaryMeta = secondary ? meta(secondary) : null

  const points = useMemo(() => {
    let rows = [...data].sort((a, b) => a.recorded_on.localeCompare(b.recorded_on))
    if (range !== 0) {
      const cutoff = new Date()
      cutoff.setDate(cutoff.getDate() - range)
      rows = rows.filter((r) => new Date(r.recorded_on) >= cutoff)
    }
    return rows.map((r) => ({
      date: new Date(r.recorded_on).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
      }),
      primary: r[primary] != null ? Number(r[primary]) : null,
      secondary: secondary && r[secondary] != null ? Number(r[secondary]) : null,
    }))
  }, [data, range, primary, secondary])

  // Есть ли хоть одна точка выбранной метрики за период (иначе — заглушка).
  const hasPrimaryPoints = points.some((p) => p.primary != null)

  if (data.length === 0) {
    return (
      <div className="card p-8 text-center">
        <TrendingDown className="h-10 w-10 mx-auto text-faint dark:text-faint-dark mb-3" />
        <p className="text-secondary text-sm">Пока нет записей.</p>
        <p className="text-xs text-tertiary mt-1">
          Добавьте первый замер — и здесь появится график прогресса.
        </p>
      </div>
    )
  }

  const chooseSecondary = (key: BodyMetric) => {
    setSecondary((cur) => (cur === key ? null : key))
  }

  return (
    <div className="card px-5 py-[18px]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[13px] font-semibold">
          Динамика · {primaryMeta.label.toLowerCase()}
        </span>
        {/* Переключатель периода: выбранный — тёмная пилюля */}
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => setRange(r.value)}
              className={`px-2.5 py-1 text-[11px] rounded-full transition-colors ${
                range === r.value
                  ? 'bg-ink text-white dark:bg-ink-dark dark:text-ink font-semibold'
                  : 'text-muted dark:text-muted-dark font-medium hover:bg-surface dark:hover:bg-chip-dark'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Переключатель основной метрики (только заполненные) */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {available.map((m) => {
          const active = m.key === primary
          return (
            <button
              key={m.key}
              onClick={() => {
                setPrimary(m.key)
                if (secondary === m.key) setSecondary(null)
              }}
              className={`px-2.5 py-1 text-[11px] rounded-full font-medium transition-colors ${
                active
                  ? 'text-white'
                  : 'text-muted dark:text-muted-dark hover:bg-surface dark:hover:bg-chip-dark'
              }`}
              style={active ? { backgroundColor: m.color } : undefined}
            >
              {m.short}
            </button>
          )
        })}
      </div>

      {/* Наложение второй метрики для сравнения (если метрик больше одной) */}
      {available.length > 1 && (
        <div className="flex flex-wrap items-center gap-1.5 mb-3.5">
          <span className="inline-flex items-center gap-1 text-[11px] text-tertiary">
            <Plus className="h-3 w-3" /> сравнить с
          </span>
          {available
            .filter((m) => m.key !== primary)
            .map((m) => {
              const active = m.key === secondary
              return (
                <button
                  key={m.key}
                  onClick={() => chooseSecondary(m.key)}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-full font-medium transition-colors ${
                    active
                      ? 'text-white'
                      : 'text-muted dark:text-muted-dark border border-divider dark:border-line-dark hover:bg-surface dark:hover:bg-chip-dark'
                  }`}
                  style={active ? { backgroundColor: m.color } : undefined}
                >
                  {m.short}
                  {active && <X className="h-3 w-3" />}
                </button>
              )
            })}
        </div>
      )}

      {!hasPrimaryPoints ? (
        <p className="py-12 text-center text-sm text-tertiary">
          Нет записей «{primaryMeta.label.toLowerCase()}» за выбранный период.
        </p>
      ) : (
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 8, right: secondaryMeta ? 8 : 8, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="0" vertical={false} stroke="#eef1f7" className="dark:opacity-20" />
              <XAxis dataKey="date" fontSize={11} tickMargin={6} stroke="#98a2b8" tickLine={false} axisLine={false} />
              <YAxis
                yAxisId="primary"
                domain={['dataMin - 2', 'dataMax + 2']}
                fontSize={11}
                unit={` ${primaryMeta.unit}`}
                width={56}
                stroke="#98a2b8"
                tickLine={false}
                axisLine={false}
              />
              {secondaryMeta && (
                <YAxis
                  yAxisId="secondary"
                  orientation="right"
                  domain={['dataMin - 2', 'dataMax + 2']}
                  fontSize={11}
                  unit={` ${secondaryMeta.unit}`}
                  width={52}
                  stroke="#98a2b8"
                  tickLine={false}
                  axisLine={false}
                />
              )}
              <Tooltip
                formatter={(v: number, name: string) => {
                  if (v == null) return ['—', name]
                  if (name === 'secondary' && secondaryMeta)
                    return [`${v} ${secondaryMeta.unit}`, secondaryMeta.label]
                  return [`${v} ${primaryMeta.unit}`, primaryMeta.label]
                }}
              />
              <Line
                yAxisId="primary"
                type="monotone"
                dataKey="primary"
                connectNulls
                stroke={primaryMeta.color}
                strokeWidth={2.5}
                dot={{ r: 3, fill: primaryMeta.color, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: primaryMeta.color, stroke: '#fff', strokeWidth: 2 }}
              />
              {secondaryMeta && (
                <Line
                  yAxisId="secondary"
                  type="monotone"
                  dataKey="secondary"
                  connectNulls
                  stroke={secondaryMeta.color}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  dot={{ r: 2.5, fill: secondaryMeta.color, strokeWidth: 0 }}
                  activeDot={{ r: 4.5, fill: secondaryMeta.color, stroke: '#fff', strokeWidth: 2 }}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
