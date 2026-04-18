import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getHouseholds, getInsights } from '../api'
import type { Household, InsightsSummary } from '../types'
import './HouseholdList.css'

function formatMoney(value?: number): string {
  if (value === undefined || value === null) return '—'
  if (Math.abs(value) >= 1_000_000)
    return `$${(value / 1_000_000).toFixed(2)}M`
  if (Math.abs(value) >= 1_000)
    return `$${(value / 1_000).toFixed(1)}K`
  return `$${value.toLocaleString()}`
}

function formatMoneyFull(value?: number): string {
  if (value === undefined || value === null) return '—'
  return '$' + value.toLocaleString('en-US', { maximumFractionDigits: 0 })
}

export default function HouseholdList() {
  const navigate = useNavigate()
  const [households, setHouseholds] = useState<Household[]>([])
  const [insights, setInsights] = useState<InsightsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    setLoading(true)
    Promise.all([getHouseholds(), getInsights()])
      .then(([hRes, iRes]) => {
        setHouseholds(hRes.data)
        setInsights(iRes.data)
      })
      .catch(() => setError('Failed to load households. Make sure the backend is running.'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = households.filter(h =>
    h.name.toLowerCase().includes(search.toLowerCase())
  )

  if (loading) {
    return (
      <div className="page-wrapper">
        <div className="spinner-wrapper">
          <div className="spinner" />
          <span>Loading households…</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-wrapper">
        <div className="error-message">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="page-wrapper">
      {/* Summary Bar */}
      {insights && (
        <div className="hl-summary-bar">
          <div className="stat-box">
            <span className="stat-box-label">Total Households</span>
            <span className="stat-box-value">{insights.total_households}</span>
            <span className="stat-box-sub">Active clients</span>
          </div>
          <div className="stat-box">
            <span className="stat-box-label">Total AUM</span>
            <span className="stat-box-value">{formatMoney(insights.total_aum)}</span>
            <span className="stat-box-sub">Assets under management</span>
          </div>
          <div className="stat-box">
            <span className="stat-box-label">Total Members</span>
            <span className="stat-box-value">{insights.total_members}</span>
            <span className="stat-box-sub">Across all households</span>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-top">
          <div>
            <h1 className="page-title">Households</h1>
            <p className="page-subtitle">Manage your client households and their financial profiles</p>
          </div>
          <div className="hl-search-wrapper">
            <svg className="hl-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              className="form-input hl-search"
              type="text"
              placeholder="Search households…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>
        {search && (
          <p className="hl-results-count">
            Showing {filtered.length} of {households.length} households
          </p>
        )}
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">🏠</div>
            <p className="empty-state-title">No households found</p>
            <p className="empty-state-sub">
              {search ? 'Try a different search term.' : 'Upload an Excel file to get started.'}
            </p>
          </div>
        </div>
      ) : (
        <div className="hl-grid">
          {filtered.map(h => (
            <div
              key={h.id}
              className="card hl-card"
              onClick={() => navigate(`/households/${h.id}`)}
              role="button"
              tabIndex={0}
              onKeyDown={e => e.key === 'Enter' && navigate(`/households/${h.id}`)}
            >
              <div className="hl-card-header">
                <div className="hl-card-avatar">
                  {h.name.charAt(0).toUpperCase()}
                </div>
                <div className="hl-card-title-group">
                  <h3 className="hl-card-name">{h.name}</h3>
                  <div className="hl-card-badges">
                    {h.risk_tolerance && (
                      <span className={`badge ${riskBadge(h.risk_tolerance)}`}>
                        {h.risk_tolerance}
                      </span>
                    )}
                    {h.tax_bracket && (
                      <span className="badge badge-gray">{h.tax_bracket}</span>
                    )}
                  </div>
                </div>
                <svg className="hl-card-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </div>

              <div className="hl-card-stats">
                <div className="hl-stat">
                  <span className="hl-stat-label">Liquid NW</span>
                  <span className="hl-stat-value">{formatMoneyFull(h.estimated_liquid_net_worth)}</span>
                </div>
                <div className="hl-stat">
                  <span className="hl-stat-label">Total NW</span>
                  <span className="hl-stat-value">{formatMoneyFull(h.estimated_total_net_worth)}</span>
                </div>
                <div className="hl-stat">
                  <span className="hl-stat-label">Annual Income</span>
                  <span className="hl-stat-value">{formatMoneyFull(h.annual_income)}</span>
                </div>
              </div>

              <div className="hl-card-footer">
                <div className="hl-meta">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                  </svg>
                  {h.member_count ?? 0} member{(h.member_count ?? 0) !== 1 ? 's' : ''}
                </div>
                <div className="hl-meta">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/>
                  </svg>
                  {h.account_count ?? 0} account{(h.account_count ?? 0) !== 1 ? 's' : ''}
                </div>
                {h.time_horizon && (
                  <div className="hl-meta">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                    </svg>
                    {h.time_horizon}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function riskBadge(risk: string): string {
  const r = risk.toLowerCase()
  if (r.includes('aggress')) return 'badge-red'
  if (r.includes('moderate')) return 'badge-yellow'
  if (r.includes('conserv')) return 'badge-green'
  return 'badge-blue'
}
