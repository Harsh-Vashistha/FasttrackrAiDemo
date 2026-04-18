import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, Sector
} from 'recharts'
import { getInsights } from '../api'
import type { InsightsSummary } from '../types'
import './Insights.css'

const CHART_COLORS = [
  '#2563eb', '#7c3aed', '#0891b2', '#059669', '#d97706',
  '#dc2626', '#db2777', '#65a30d', '#9333ea', '#0284c7'
]

const PIE_COLORS = [
  '#2563eb', '#7c3aed', '#0891b2', '#059669', '#d97706',
  '#dc2626', '#db2777', '#9333ea', '#65a30d', '#0284c7'
]

function formatMoneyShort(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return `$${value}`
}

function shortName(name: string): string {
  const parts = name.split(' ')
  if (parts.length >= 2) return `${parts[0][0]}. ${parts[parts.length - 1]}`
  return name.length > 10 ? name.slice(0, 10) + '…' : name
}

function CustomTooltipMoney({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-label">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="chart-tooltip-row">
          <span className="chart-tooltip-dot" style={{ background: p.color }} />
          <span className="chart-tooltip-name">{p.name}:</span>
          <span className="chart-tooltip-value">{formatMoneyShort(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

function CustomTooltipCount({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-label">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="chart-tooltip-row">
          <span className="chart-tooltip-dot" style={{ background: p.color }} />
          <span className="chart-tooltip-name">{p.name}:</span>
          <span className="chart-tooltip-value">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderActiveShape(props: any) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload, value, percent } = props as {
    cx: number; cy: number; innerRadius: number; outerRadius: number;
    startAngle: number; endAngle: number; fill: string; payload: { name: string };
    value: number; percent: number;
  }
  return (
    <g>
      <text x={cx} y={cy - 12} textAnchor="middle" fill="#0f172a" className="pie-center-title">
        {payload.name}
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" fill="#2563eb" className="pie-center-value">
        {value} ({(percent * 100).toFixed(0)}%)
      </text>
      <Sector cx={cx} cy={cy} innerRadius={innerRadius} outerRadius={outerRadius + 8} startAngle={startAngle} endAngle={endAngle} fill={fill} />
      <Sector cx={cx} cy={cy} innerRadius={outerRadius + 12} outerRadius={outerRadius + 16} startAngle={startAngle} endAngle={endAngle} fill={fill} />
    </g>
  )
}

export default function Insights() {
  const [data, setData] = useState<InsightsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeAccountIdx, setActiveAccountIdx] = useState(0)
  const [activeTaxIdx, setActiveTaxIdx] = useState(0)
  const [activeRiskIdx, setActiveRiskIdx] = useState(0)

  useEffect(() => {
    getInsights()
      .then(r => setData(r.data))
      .catch(() => setError('Failed to load insights. Make sure the backend is running.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="page-wrapper">
        <div className="spinner-wrapper">
          <div className="spinner" />
          <span>Loading insights…</span>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="page-wrapper">
        <div className="error-message">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          {error || 'No data available.'}
        </div>
      </div>
    )
  }

  const topNetWorth = [...data.households_by_net_worth]
    .sort((a, b) => b.total_net_worth - a.total_net_worth)
    .slice(0, 10)
    .map(h => ({ ...h, name: shortName(h.name) }))

  const topIncome = [...data.income_distribution]
    .sort((a, b) => b.annual_income - a.annual_income)
    .slice(0, 10)
    .map(h => ({ ...h, name: shortName(h.name) }))

  const accountData = data.account_type_distribution.map(d => ({ name: d.account_type, value: d.count }))
  const taxData = data.tax_bracket_distribution.map(d => ({ name: d.bracket, value: d.count }))
  const riskData = data.risk_tolerance_distribution.map(d => ({ name: d.risk, value: d.count }))
  const membersData = data.members_per_household.map(d => ({
    name: shortName(d.household_name),
    members: d.member_count
  }))

  return (
    <div className="page-wrapper">
      <div className="page-header">
        <h1 className="page-title">Insights</h1>
        <p className="page-subtitle">Portfolio analytics and client distribution overview</p>
      </div>

      {/* Summary KPIs */}
      <div className="ins-kpi-row">
        <div className="stat-box">
          <span className="stat-box-label">Total AUM</span>
          <span className="stat-box-value">{formatMoneyShort(data.total_aum)}</span>
        </div>
        <div className="stat-box">
          <span className="stat-box-label">Households</span>
          <span className="stat-box-value">{data.total_households}</span>
        </div>
        <div className="stat-box">
          <span className="stat-box-label">Members</span>
          <span className="stat-box-value">{data.total_members}</span>
        </div>
        <div className="stat-box">
          <span className="stat-box-label">Avg AUM / Household</span>
          <span className="stat-box-value">
            {data.total_households > 0 ? formatMoneyShort(data.total_aum / data.total_households) : '—'}
          </span>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="ins-charts-grid">

        {/* 1. Net Worth by Household */}
        <div className="card card-padded ins-chart-card ins-chart-wide">
          <div className="section-header">
            <h3 className="section-title">
              <span className="section-title-dot" />
              Net Worth by Household
            </h3>
            <span className="badge badge-gray">Top 10</span>
          </div>
          {topNetWorth.length === 0 ? (
            <div className="empty-state"><p className="empty-state-title">No data</p></div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={topNetWorth} margin={{ top: 4, right: 8, left: 8, bottom: 40 }} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} angle={-30} textAnchor="end" interval={0} />
                <YAxis tickFormatter={formatMoneyShort} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltipMoney />} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                <Bar dataKey="liquid_net_worth" name="Liquid NW" fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="total_net_worth" name="Total NW" fill="#7c3aed" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 2. Annual Income */}
        <div className="card card-padded ins-chart-card ins-chart-wide">
          <div className="section-header">
            <h3 className="section-title">
              <span className="section-title-dot" style={{ background: '#0891b2' }} />
              Annual Income by Household
            </h3>
            <span className="badge badge-gray">Top 10</span>
          </div>
          {topIncome.length === 0 ? (
            <div className="empty-state"><p className="empty-state-title">No data</p></div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={topIncome} margin={{ top: 4, right: 8, left: 8, bottom: 40 }} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} angle={-30} textAnchor="end" interval={0} />
                <YAxis tickFormatter={formatMoneyShort} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltipMoney />} />
                <Bar dataKey="annual_income" name="Annual Income" fill="#0891b2" radius={[4, 4, 0, 0]}>
                  {topIncome.map((_entry, index) => (
                    <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 3. Account Types Pie */}
        <div className="card card-padded ins-chart-card">
          <div className="section-header">
            <h3 className="section-title">
              <span className="section-title-dot" style={{ background: '#059669' }} />
              Account Types
            </h3>
          </div>
          {accountData.length === 0 ? (
            <div className="empty-state"><p className="empty-state-title">No data</p></div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  activeIndex={activeAccountIdx}
                  activeShape={renderActiveShape}
                  data={accountData}
                  cx="50%"
                  cy="50%"
                  innerRadius={70}
                  outerRadius={100}
                  dataKey="value"
                  onMouseEnter={(_, idx) => setActiveAccountIdx(idx)}
                >
                  {accountData.map((_entry, index) => (
                    <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => [v, 'Count']} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="ins-pie-legend">
            {accountData.map((d, i) => (
              <div key={i} className="ins-legend-item">
                <span className="ins-legend-dot" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                <span className="ins-legend-name">{d.name}</span>
                <span className="ins-legend-value">{d.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 4. Tax Bracket */}
        <div className="card card-padded ins-chart-card">
          <div className="section-header">
            <h3 className="section-title">
              <span className="section-title-dot" style={{ background: '#d97706' }} />
              Tax Bracket Distribution
            </h3>
          </div>
          {taxData.length === 0 ? (
            <div className="empty-state"><p className="empty-state-title">No data</p></div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  activeIndex={activeTaxIdx}
                  activeShape={renderActiveShape}
                  data={taxData}
                  cx="50%"
                  cy="50%"
                  innerRadius={70}
                  outerRadius={100}
                  dataKey="value"
                  onMouseEnter={(_, idx) => setActiveTaxIdx(idx)}
                >
                  {taxData.map((_entry, index) => (
                    <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => [v, 'Households']} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="ins-pie-legend">
            {taxData.map((d, i) => (
              <div key={i} className="ins-legend-item">
                <span className="ins-legend-dot" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                <span className="ins-legend-name">{d.name}</span>
                <span className="ins-legend-value">{d.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 5. Risk Tolerance */}
        <div className="card card-padded ins-chart-card">
          <div className="section-header">
            <h3 className="section-title">
              <span className="section-title-dot" style={{ background: '#dc2626' }} />
              Risk Tolerance
            </h3>
          </div>
          {riskData.length === 0 ? (
            <div className="empty-state"><p className="empty-state-title">No data</p></div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  activeIndex={activeRiskIdx}
                  activeShape={renderActiveShape}
                  data={riskData}
                  cx="50%"
                  cy="50%"
                  innerRadius={70}
                  outerRadius={100}
                  dataKey="value"
                  onMouseEnter={(_, idx) => setActiveRiskIdx(idx)}
                >
                  {riskData.map((_entry, index) => (
                    <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => [v, 'Households']} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="ins-pie-legend">
            {riskData.map((d, i) => (
              <div key={i} className="ins-legend-item">
                <span className="ins-legend-dot" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                <span className="ins-legend-name">{d.name}</span>
                <span className="ins-legend-value">{d.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 6. Members per Household */}
        <div className="card card-padded ins-chart-card ins-chart-wide">
          <div className="section-header">
            <h3 className="section-title">
              <span className="section-title-dot" style={{ background: '#9333ea' }} />
              Members per Household
            </h3>
          </div>
          {membersData.length === 0 ? (
            <div className="empty-state"><p className="empty-state-title">No data</p></div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={membersData} margin={{ top: 4, right: 8, left: 8, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} angle={-30} textAnchor="end" interval={0} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltipCount />} />
                <Bar dataKey="members" name="Members" radius={[4, 4, 0, 0]}>
                  {membersData.map((_entry, index) => (
                    <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

      </div>
    </div>
  )
}
