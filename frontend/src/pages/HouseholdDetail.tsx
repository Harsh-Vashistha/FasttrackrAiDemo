import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getHousehold, updateHousehold, getAudioInsights, getActionItems, updateActionItemStatus } from '../api'
import type { Household, AudioInsight, ActionItem } from '../types'
import './HouseholdDetail.css'

function formatMoney(value?: number): string {
  if (value === undefined || value === null) return '—'
  return '$' + value.toLocaleString('en-US', { maximumFractionDigits: 0 })
}

function maskAccountNumber(num?: string): string {
  if (!num) return '—'
  if (num.length <= 4) return `****${num}`
  return `****${num.slice(-4)}`
}

function formatDate(dob?: string): string {
  if (!dob) return '—'
  try {
    return new Date(dob).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return dob
  }
}

type EditableFields = Pick<Household,
  'estimated_liquid_net_worth' | 'estimated_total_net_worth' | 'annual_income' |
  'tax_bracket' | 'risk_tolerance' | 'time_horizon' | 'primary_investment_objective'
>

export default function HouseholdDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [household, setHousehold] = useState<Household | null>(null)
  const [audioInsights, setAudioInsights] = useState<AudioInsight[]>([])
  const [actionItems, setActionItems] = useState<ActionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editValues, setEditValues] = useState<Partial<EditableFields>>({})
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    const numId = parseInt(id, 10)
    Promise.all([
      getHousehold(numId),
      getAudioInsights(numId).catch(() => ({ data: [] })),
      getActionItems(numId).catch(() => ({ data: [] })),
    ])
      .then(([hRes, aRes, acRes]) => {
        setHousehold(hRes.data)
        setAudioInsights(aRes.data)
        setActionItems(acRes.data)
      })
      .catch(() => setError('Failed to load household details.'))
      .finally(() => setLoading(false))
  }, [id])

  const handleEditStart = () => {
    if (!household) return
    setEditValues({
      estimated_liquid_net_worth: household.estimated_liquid_net_worth,
      estimated_total_net_worth: household.estimated_total_net_worth,
      annual_income: household.annual_income,
      tax_bracket: household.tax_bracket,
      risk_tolerance: household.risk_tolerance,
      time_horizon: household.time_horizon,
      primary_investment_objective: household.primary_investment_objective,
    })
    setEditing(true)
  }

  const handleSave = async () => {
    if (!id || !household) return
    setSaving(true)
    try {
      const res = await updateHousehold(parseInt(id, 10), editValues)
      setHousehold(res.data)
      setEditing(false)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch {
      setError('Failed to save changes.')
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditing(false)
    setEditValues({})
  }

  if (loading) {
    return (
      <div className="page-wrapper">
        <div className="spinner-wrapper">
          <div className="spinner" />
          <span>Loading household details…</span>
        </div>
      </div>
    )
  }

  if (error || !household) {
    return (
      <div className="page-wrapper">
        <button className="btn btn-ghost btn-sm hd-back" onClick={() => navigate('/households')}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          Back to Households
        </button>
        <div className="error-message" style={{ marginTop: 16 }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          {error || 'Household not found.'}
        </div>
      </div>
    )
  }

  return (
    <div className="page-wrapper">
      {/* Back */}
      <button className="btn btn-ghost btn-sm hd-back" onClick={() => navigate('/households')}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
        Back to Households
      </button>

      {/* Header */}
      <div className="hd-header card card-padded">
        <div className="hd-header-top">
          <div className="hd-header-avatar">
            {household.name.charAt(0).toUpperCase()}
          </div>
          <div className="hd-header-info">
            <h1 className="hd-household-name">{household.name}</h1>
            <div className="hd-header-meta">
              {household.primary_investment_objective && (
                <span className="badge badge-blue">{household.primary_investment_objective}</span>
              )}
              {household.risk_tolerance && (
                <span className={`badge ${riskBadge(household.risk_tolerance)}`}>
                  {household.risk_tolerance} Risk
                </span>
              )}
              {household.time_horizon && (
                <span className="badge badge-gray">{household.time_horizon} horizon</span>
              )}
            </div>
          </div>
          <div className="hd-header-actions">
            {saveSuccess && (
              <span className="hd-save-success">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Saved
              </span>
            )}
            {editing ? (
              <>
                <button className="btn btn-secondary btn-sm" onClick={handleCancel} disabled={saving}>
                  Cancel
                </button>
                <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
                  {saving ? <><div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} />Saving…</> : 'Save Changes'}
                </button>
              </>
            ) : (
              <button className="btn btn-secondary btn-sm" onClick={handleEditStart}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                Edit
              </button>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="hd-stats-grid">
          <div className="stat-box">
            <span className="stat-box-label">Liquid Net Worth</span>
            {editing ? (
              <input
                className="form-input"
                type="number"
                value={editValues.estimated_liquid_net_worth ?? ''}
                onChange={e => setEditValues(v => ({ ...v, estimated_liquid_net_worth: e.target.value ? Number(e.target.value) : undefined }))}
              />
            ) : (
              <span className="stat-box-value">{formatMoney(household.estimated_liquid_net_worth)}</span>
            )}
          </div>
          <div className="stat-box">
            <span className="stat-box-label">Total Net Worth</span>
            {editing ? (
              <input
                className="form-input"
                type="number"
                value={editValues.estimated_total_net_worth ?? ''}
                onChange={e => setEditValues(v => ({ ...v, estimated_total_net_worth: e.target.value ? Number(e.target.value) : undefined }))}
              />
            ) : (
              <span className="stat-box-value">{formatMoney(household.estimated_total_net_worth)}</span>
            )}
          </div>
          <div className="stat-box">
            <span className="stat-box-label">Annual Income</span>
            {editing ? (
              <input
                className="form-input"
                type="number"
                value={editValues.annual_income ?? ''}
                onChange={e => setEditValues(v => ({ ...v, annual_income: e.target.value ? Number(e.target.value) : undefined }))}
              />
            ) : (
              <span className="stat-box-value">{formatMoney(household.annual_income)}</span>
            )}
          </div>
          <div className="stat-box">
            <span className="stat-box-label">Tax Bracket</span>
            {editing ? (
              <input
                className="form-input"
                type="text"
                value={editValues.tax_bracket ?? ''}
                onChange={e => setEditValues(v => ({ ...v, tax_bracket: e.target.value }))}
              />
            ) : (
              <span className="stat-box-value" style={{ fontSize: '1.25rem' }}>{household.tax_bracket ?? '—'}</span>
            )}
          </div>
          <div className="stat-box">
            <span className="stat-box-label">Risk Tolerance</span>
            {editing ? (
              <select
                className="form-input form-select"
                value={editValues.risk_tolerance ?? ''}
                onChange={e => setEditValues(v => ({ ...v, risk_tolerance: e.target.value }))}
              >
                <option value="">Select…</option>
                <option>Conservative</option>
                <option>Moderate</option>
                <option>Aggressive</option>
                <option>Moderate-Conservative</option>
                <option>Moderate-Aggressive</option>
              </select>
            ) : (
              <span className="stat-box-value" style={{ fontSize: '1.125rem' }}>{household.risk_tolerance ?? '—'}</span>
            )}
          </div>
          <div className="stat-box">
            <span className="stat-box-label">Time Horizon</span>
            {editing ? (
              <input
                className="form-input"
                type="text"
                value={editValues.time_horizon ?? ''}
                onChange={e => setEditValues(v => ({ ...v, time_horizon: e.target.value }))}
              />
            ) : (
              <span className="stat-box-value" style={{ fontSize: '1.125rem' }}>{household.time_horizon ?? '—'}</span>
            )}
          </div>
        </div>
      </div>

      {/* Members */}
      <div className="hd-section">
        <div className="section-header">
          <h2 className="section-title">
            <span className="section-title-dot" />
            Members
            <span className="badge badge-gray">{household.members?.length ?? 0}</span>
          </h2>
        </div>
        {(!household.members || household.members.length === 0) ? (
          <div className="card"><div className="empty-state"><p className="empty-state-title">No members</p></div></div>
        ) : (
          <div className="card">
            <div className="table-container" style={{ border: 'none' }}>
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Date of Birth</th>
                    <th>Occupation</th>
                    <th>Employer</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Marital Status</th>
                  </tr>
                </thead>
                <tbody>
                  {household.members.map(m => (
                    <tr key={m.id}>
                      <td>
                        <div className="hd-member-name">
                          <div className="hd-member-avatar">
                            {m.first_name.charAt(0)}{m.last_name.charAt(0)}
                          </div>
                          {m.first_name} {m.last_name}
                        </div>
                      </td>
                      <td>{formatDate(m.dob)}</td>
                      <td>{m.occupation ?? '—'}</td>
                      <td>{m.employer ?? '—'}</td>
                      <td>
                        {m.email ? (
                          <a href={`mailto:${m.email}`} style={{ color: 'var(--color-accent)' }}>{m.email}</a>
                        ) : '—'}
                      </td>
                      <td>{m.phone ?? '—'}</td>
                      <td>
                        {m.marital_status ? (
                          <span className="badge badge-gray">{m.marital_status}</span>
                        ) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Accounts */}
      <div className="hd-section">
        <div className="section-header">
          <h2 className="section-title">
            <span className="section-title-dot" />
            Accounts
            <span className="badge badge-gray">{household.accounts?.length ?? 0}</span>
          </h2>
        </div>
        {(!household.accounts || household.accounts.length === 0) ? (
          <div className="card"><div className="empty-state"><p className="empty-state-title">No accounts</p></div></div>
        ) : (
          <div className="card">
            <div className="table-container" style={{ border: 'none' }}>
              <table>
                <thead>
                  <tr>
                    <th>Account Type</th>
                    <th>Custodian</th>
                    <th>Account Number</th>
                    <th>Account Value</th>
                  </tr>
                </thead>
                <tbody>
                  {household.accounts.map(a => (
                    <tr key={a.id}>
                      <td>
                        <span className="badge badge-blue">{a.account_type}</span>
                      </td>
                      <td>{a.custodian ?? '—'}</td>
                      <td>
                        <span className="hd-acct-num">{maskAccountNumber(a.account_number)}</span>
                      </td>
                      <td>{formatMoney(a.account_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Bank Details */}
      {household.members?.some(m => m.bank_details && m.bank_details.length > 0) && (
        <div className="hd-section">
          <div className="section-header">
            <h2 className="section-title">
              <span className="section-title-dot" />
              Bank Details
            </h2>
          </div>
          <div className="hd-bank-grid">
            {household.members.map(m =>
              m.bank_details && m.bank_details.length > 0 ? (
                <div key={m.id} className="card card-padded">
                  <div className="hd-bank-member">
                    <div className="hd-member-avatar">{m.first_name.charAt(0)}{m.last_name.charAt(0)}</div>
                    <span className="hd-bank-member-name">{m.first_name} {m.last_name}</span>
                  </div>
                  <div className="table-container" style={{ marginTop: 12 }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Bank Name</th>
                          <th>Type</th>
                          <th>Account #</th>
                        </tr>
                      </thead>
                      <tbody>
                        {m.bank_details.map(b => (
                          <tr key={b.id}>
                            <td>{b.bank_name ?? '—'}</td>
                            <td>{b.bank_type ?? '—'}</td>
                            <td><span className="hd-acct-num">{maskAccountNumber(b.account_number)}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null
            )}
          </div>
        </div>
      )}

      {/* Action Items */}
      {actionItems.length > 0 && (
        <div className="hd-section">
          <div className="section-header">
            <h2 className="section-title">
              <span className="section-title-dot" style={{ background: '#f59e0b' }} />
              Action Items
              <span className="badge" style={{ background: '#fef3c7', color: '#92400e' }}>
                {actionItems.filter(i => i.status === 'pending').length} pending
              </span>
            </h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {actionItems.map(item => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  padding: '12px 16px',
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 8,
                  opacity: item.status === 'completed' ? 0.6 : 1,
                  transition: 'opacity 0.2s',
                }}
              >
                {/* Checkbox */}
                <button
                  onClick={async () => {
                    const newStatus = item.status === 'completed' ? 'pending' : 'completed'
                    const res = await updateActionItemStatus(household!.id, item.id, newStatus)
                    setActionItems(prev => prev.map(i => i.id === item.id ? res.data : i))
                  }}
                  style={{
                    flexShrink: 0,
                    marginTop: 2,
                    width: 20,
                    height: 20,
                    borderRadius: 4,
                    border: `2px solid ${item.status === 'completed' ? '#22c55e' : 'var(--color-border)'}`,
                    background: item.status === 'completed' ? '#22c55e' : 'transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 0,
                  }}
                >
                  {item.status === 'completed' && (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  )}
                </button>

                {/* Description */}
                <span style={{
                  flex: 1,
                  fontSize: '0.9rem',
                  color: 'var(--color-text)',
                  textDecoration: item.status === 'completed' ? 'line-through' : 'none',
                  lineHeight: 1.5,
                }}>
                  {item.description}
                </span>

                {/* Date + status */}
                <div style={{ flexShrink: 0, textAlign: 'right' }}>
                  <span style={{
                    fontSize: '0.75rem',
                    color: 'var(--color-text-muted)',
                    display: 'block',
                  }}>
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                  {item.status === 'completed' && item.completed_at && (
                    <span style={{ fontSize: '0.7rem', color: '#22c55e' }}>
                      ✓ {new Date(item.completed_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Audio Insights */}
      {audioInsights.length > 0 && (
        <div className="hd-section">
          <div className="section-header">
            <h2 className="section-title">
              <span className="section-title-dot" style={{ background: '#7c3aed' }} />
              Audio Insights
              <span className="badge" style={{ background: '#ede9fe', color: '#6d28d9' }}>{audioInsights.length}</span>
            </h2>
          </div>
          <div className="hd-audio-list">
            {audioInsights.map((ai, idx) => (
              <div key={ai.id} className="card card-padded hd-audio-card">
                <div className="hd-audio-header">
                  <div className="hd-audio-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/>
                      <line x1="8" y1="23" x2="16" y2="23"/>
                    </svg>
                  </div>
                  <div>
                    <h4 className="hd-audio-title">Recording {idx + 1}</h4>
                    {ai.created_at && (
                      <span className="hd-audio-date">{new Date(ai.created_at).toLocaleString()}</span>
                    )}
                  </div>
                </div>

                {ai.transcription && (
                  <div className="hd-transcription">
                    <h5 className="hd-insight-label">Transcription</h5>
                    <p className="hd-transcription-text">{ai.transcription}</p>
                  </div>
                )}

                {ai.extracted_data?.key_insights && ai.extracted_data.key_insights.length > 0 && (
                  <div className="hd-insights-block">
                    <h5 className="hd-insight-label">Key Insights</h5>
                    <ul className="hd-insights-list">
                      {ai.extracted_data.key_insights.map((ins, i) => (
                        <li key={i}>{ins}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Action items now live in the dedicated Action Items section above */}
              </div>
            ))}
          </div>
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
