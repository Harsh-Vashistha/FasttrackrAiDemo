import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import type { ReviewSession, ProposedChange } from '../types'
import client from '../api'

// ─── Status badge colors ────────────────────────────────────────────────────

function badgeStyle(status: string): React.CSSProperties {
  const map: Record<string, { bg: string; color: string }> = {
    pending:          { bg: '#f59e0b22', color: '#f59e0b' },
    approved:         { bg: '#22c55e22', color: '#22c55e' },
    rejected:         { bg: '#ef444422', color: '#ef4444' },
    pending_revision: { bg: '#3b82f622', color: '#3b82f6' },
    revised:          { bg: '#8b5cf622', color: '#8b5cf6' },
    dismissed:        { bg: '#6b728022', color: '#6b7280' },
  }
  const s = map[status] ?? { bg: '#6b728022', color: '#6b7280' }
  return {
    fontSize: '0.75rem',
    fontWeight: 600,
    padding: '2px 10px',
    borderRadius: 20,
    background: s.bg,
    color: s.color,
    textTransform: 'capitalize',
    whiteSpace: 'nowrap',
  }
}

function sessionStatusColor(status: string): string {
  switch (status) {
    case 'completed': return '#22c55e'
    case 'pending': return '#f59e0b'
    case 'in_review': return '#3b82f6'
    default: return '#6b7280'
  }
}

// ─── Confidence bar ─────────────────────────────────────────────────────────

function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null || value === undefined) return null
  const pct = Math.round(value * 100)
  const color = value >= 0.8 ? '#22c55e' : value >= 0.5 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 4 }}>
        <span>Confidence</span>
        <span style={{ color, fontWeight: 600 }}>{pct}%</span>
      </div>
      <div style={{ height: 4, background: 'var(--color-border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.3s ease' }} />
      </div>
    </div>
  )
}

// ─── Individual change card ──────────────────────────────────────────────────

interface ChangeCardProps {
  change: ProposedChange
  sessionId: number
  onUpdate: (updated: ProposedChange) => void
}

function ChangeCard({ change, sessionId, onUpdate }: ChangeCardProps) {
  const [rejectMode, setRejectMode] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleApprove = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await client.post<ProposedChange>(`/review/${sessionId}/changes/${change.id}/approve`)
      onUpdate(r.data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleRejectSubmit = async () => {
    if (!feedback.trim()) return
    setLoading(true)
    setError(null)
    try {
      const r = await client.post<ProposedChange>(`/review/${sessionId}/changes/${change.id}/reject`, { feedback })
      onUpdate(r.data)
      setRejectMode(false)
      setFeedback('')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAcceptRevision = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await client.post<ProposedChange>(`/review/${sessionId}/changes/${change.id}/accept-revision`)
      onUpdate(r.data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleStillWrong = () => {
    setRejectMode(true)
    setFeedback('')
  }

  const isDimmed = change.status === 'dismissed' || change.status === 'rejected'
  const isApproved = change.status === 'approved'

  return (
    <div style={{
      background: 'var(--color-surface)',
      border: `1px solid ${isApproved ? '#22c55e44' : isDimmed ? 'var(--color-border)' : 'var(--color-border)'}`,
      borderRadius: 10,
      padding: '18px 20px',
      opacity: isDimmed ? 0.6 : 1,
      transition: 'opacity 0.2s',
    }}>
      {/* Title row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
        <span style={{ fontWeight: 600, fontSize: '0.9375rem', color: 'var(--color-text)' }}>
          {change.entity_label || change.entity_type} → <code style={{ fontFamily: 'monospace', fontSize: '0.875rem', color: 'var(--color-accent)' }}>{change.field_name}</code>
        </span>
        <span style={badgeStyle(change.status)}>{change.status.replace('_', ' ')}</span>
      </div>

      {/* Value columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
            Current Value
          </div>
          <div style={{
            background: 'var(--color-bg)',
            border: '1px solid var(--color-border)',
            borderRadius: 6,
            padding: '8px 12px',
            fontSize: '0.9rem',
            color: change.current_value ? 'var(--color-text)' : 'var(--color-text-muted)',
            fontStyle: change.current_value ? 'normal' : 'italic',
          }}>
            {change.current_value ?? '— new —'}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
            Proposed Value
          </div>
          <div style={{
            background: 'var(--color-bg)',
            border: `1px solid ${change.status === 'revised' ? '#8b5cf644' : 'var(--color-border)'}`,
            borderRadius: 6,
            padding: '8px 12px',
            fontSize: '0.9rem',
            color: 'var(--color-text)',
            fontWeight: change.status === 'revised' ? 600 : 400,
          }}>
            {change.status === 'revised' && change.revised_value
              ? change.revised_value
              : change.proposed_value ?? '—'}
            {change.status === 'revised' && (
              <span style={{ marginLeft: 8, fontSize: '0.75rem', color: '#8b5cf6', fontWeight: 400 }}>(revised)</span>
            )}
          </div>
        </div>
      </div>

      {/* Source quote */}
      {change.source_quote && (
        <blockquote style={{
          margin: '0 0 12px 0',
          padding: '8px 14px',
          borderLeft: '3px solid var(--color-accent)',
          background: 'var(--color-bg)',
          borderRadius: '0 6px 6px 0',
          fontSize: '0.875rem',
          color: 'var(--color-text-muted)',
          fontStyle: 'italic',
          lineHeight: 1.5,
        }}>
          "{change.source_quote}"
        </blockquote>
      )}

      {/* Revised source quote if different */}
      {change.status === 'revised' && change.revised_source_quote && change.revised_source_quote !== change.source_quote && (
        <blockquote style={{
          margin: '0 0 12px 0',
          padding: '8px 14px',
          borderLeft: '3px solid #8b5cf6',
          background: 'var(--color-bg)',
          borderRadius: '0 6px 6px 0',
          fontSize: '0.875rem',
          color: '#8b5cf6',
          fontStyle: 'italic',
          lineHeight: 1.5,
        }}>
          Revised quote: "{change.revised_source_quote}"
        </blockquote>
      )}

      {/* Confidence bar */}
      <ConfidenceBar value={
        change.status === 'revised' && change.revised_confidence !== null
          ? change.revised_confidence
          : change.confidence
      } />

      {/* Reasoning */}
      {change.reasoning && (
        <p style={{ marginTop: 10, fontSize: '0.8125rem', color: 'var(--color-text-muted)', lineHeight: 1.5 }}>
          {change.reasoning}
        </p>
      )}

      {/* Agent response (for revised/dismissed) */}
      {change.agent_response && (change.status === 'revised' || change.status === 'dismissed') && (
        <div style={{
          marginTop: 12,
          padding: '10px 14px',
          background: change.status === 'dismissed' ? '#6b728011' : '#8b5cf611',
          border: `1px solid ${change.status === 'dismissed' ? '#6b728033' : '#8b5cf633'}`,
          borderRadius: 8,
          fontSize: '0.8125rem',
          color: change.status === 'dismissed' ? 'var(--color-text-muted)' : '#8b5cf6',
          lineHeight: 1.5,
        }}>
          <span style={{ fontWeight: 600 }}>Agent: </span>{change.agent_response}
        </div>
      )}

      {/* Dismissed label */}
      {change.status === 'dismissed' && (
        <div style={{ marginTop: 10, fontSize: '0.8125rem', color: '#6b7280', fontStyle: 'italic' }}>
          Agent agreed — dismissed
        </div>
      )}

      {/* Approved indicator */}
      {isApproved && (
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 6, color: '#22c55e', fontSize: '0.875rem', fontWeight: 600 }}>
          <span>✓</span> Approved
        </div>
      )}

      {/* pending_revision spinner */}
      {change.status === 'pending_revision' && (
        <div style={{ marginTop: 12, color: '#3b82f6', fontSize: '0.875rem' }}>
          Agent is re-analyzing...
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ marginTop: 10, fontSize: '0.8125rem', color: '#ef4444' }}>
          Error: {error}
        </div>
      )}

      {/* Actions */}
      {change.status === 'pending' && !rejectMode && (
        <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
          <button
            onClick={handleApprove}
            disabled={loading}
            style={{
              background: '#22c55e22',
              color: '#22c55e',
              border: '1px solid #22c55e44',
              borderRadius: 8,
              padding: '7px 18px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '0.875rem',
              transition: 'all 0.15s',
            }}
          >
            {loading ? '...' : '✓ Approve'}
          </button>
          <button
            onClick={() => setRejectMode(true)}
            disabled={loading}
            style={{
              background: '#ef444422',
              color: '#ef4444',
              border: '1px solid #ef444444',
              borderRadius: 8,
              padding: '7px 18px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '0.875rem',
              transition: 'all 0.15s',
            }}
          >
            ✗ Reject
          </button>
        </div>
      )}

      {/* Reject feedback input */}
      {rejectMode && change.status === 'pending' && (
        <div style={{ marginTop: 14 }}>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="Explain what's wrong with this proposed change..."
            rows={3}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              padding: '10px 12px',
              color: 'var(--color-text)',
              fontSize: '0.875rem',
              resize: 'vertical',
              outline: 'none',
            }}
          />
          <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
            <button
              onClick={handleRejectSubmit}
              disabled={loading || !feedback.trim()}
              style={{
                background: 'var(--color-accent)',
                color: 'white',
                border: 'none',
                borderRadius: 8,
                padding: '7px 18px',
                cursor: loading || !feedback.trim() ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                fontSize: '0.875rem',
                opacity: loading || !feedback.trim() ? 0.6 : 1,
              }}
            >
              {loading ? 'Sending to Agent...' : 'Send to Agent'}
            </button>
            <button
              onClick={() => { setRejectMode(false); setFeedback('') }}
              disabled={loading}
              style={{
                background: 'transparent',
                color: 'var(--color-text-muted)',
                border: '1px solid var(--color-border)',
                borderRadius: 8,
                padding: '7px 14px',
                cursor: 'pointer',
                fontSize: '0.875rem',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Revised actions */}
      {change.status === 'revised' && !rejectMode && (
        <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
          <button
            onClick={handleAcceptRevision}
            disabled={loading}
            style={{
              background: '#8b5cf622',
              color: '#8b5cf6',
              border: '1px solid #8b5cf644',
              borderRadius: 8,
              padding: '7px 18px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '0.875rem',
            }}
          >
            {loading ? '...' : '✓ Accept Revision'}
          </button>
          <button
            onClick={handleStillWrong}
            disabled={loading}
            style={{
              background: '#ef444422',
              color: '#ef4444',
              border: '1px solid #ef444444',
              borderRadius: 8,
              padding: '7px 18px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: '0.875rem',
            }}
          >
            ✗ Still Wrong
          </button>
        </div>
      )}

      {/* Re-reject feedback for revised state */}
      {rejectMode && change.status === 'revised' && (
        <div style={{ marginTop: 14 }}>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="What's still wrong? Provide more specific feedback..."
            rows={3}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              background: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              padding: '10px 12px',
              color: 'var(--color-text)',
              fontSize: '0.875rem',
              resize: 'vertical',
              outline: 'none',
            }}
          />
          <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
            <button
              onClick={handleRejectSubmit}
              disabled={loading || !feedback.trim()}
              style={{
                background: 'var(--color-accent)',
                color: 'white',
                border: 'none',
                borderRadius: 8,
                padding: '7px 18px',
                cursor: loading || !feedback.trim() ? 'not-allowed' : 'pointer',
                fontWeight: 600,
                fontSize: '0.875rem',
                opacity: loading || !feedback.trim() ? 0.6 : 1,
              }}
            >
              {loading ? 'Sending to Agent...' : 'Send to Agent'}
            </button>
            <button
              onClick={() => { setRejectMode(false); setFeedback('') }}
              disabled={loading}
              style={{
                background: 'transparent',
                color: 'var(--color-text-muted)',
                border: '1px solid var(--color-border)',
                borderRadius: 8,
                padding: '7px 14px',
                cursor: 'pointer',
                fontSize: '0.875rem',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function ReviewDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [session, setSession] = useState<ReviewSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [applying, setApplying] = useState(false)
  const [applyResult, setApplyResult] = useState<string | null>(null)

  const fetchSession = useCallback(() => {
    if (!id) return
    setLoading(true)
    client.get<ReviewSession>(`/review/${id}`)
      .then(r => setSession(r.data))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { fetchSession() }, [fetchSession])

  const handleChangeUpdate = useCallback((updated: ProposedChange) => {
    setSession(prev => {
      if (!prev) return prev
      return {
        ...prev,
        proposed_changes: prev.proposed_changes.map(c => c.id === updated.id ? updated : c),
      }
    })
  }, [])

  const handleApply = async () => {
    if (!id) return
    setApplying(true)
    setApplyResult(null)
    try {
      const r = await client.post<{ applied: number; skipped: number; message: string }>(`/review/${id}/apply`)
      setApplyResult(r.data.message)
      fetchSession()
    } catch (e: any) {
      setApplyResult(`Error: ${e.message}`)
    } finally {
      setApplying(false)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
        Loading session...
      </div>
    )
  }

  if (error || !session) {
    return (
      <div style={{ padding: '48px 24px', textAlign: 'center', color: '#ef4444' }}>
        {error || 'Session not found'}
        <div style={{ marginTop: 16 }}>
          <button onClick={() => navigate('/review')} style={{ color: 'var(--color-accent)', background: 'none', border: 'none', cursor: 'pointer' }}>
            ← Back to queue
          </button>
        </div>
      </div>
    )
  }

  // Group changes by entity_label
  const groups: Record<string, ProposedChange[]> = {}
  for (const change of session.proposed_changes) {
    const key = change.entity_label || change.entity_type || 'Other'
    groups[key] = groups[key] ?? []
    groups[key].push(change)
  }

  const approvedCount = session.proposed_changes.filter(c => c.status === 'approved').length
  const canApply = approvedCount > 0 && session.status !== 'completed'

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
      {/* Back link */}
      <button
        onClick={() => navigate('/review')}
        style={{ background: 'none', border: 'none', color: 'var(--color-accent)', cursor: 'pointer', fontSize: '0.9rem', marginBottom: 20, padding: 0 }}
      >
        ← Back to Review Queue
      </button>

      {/* Session header */}
      <div style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 12,
        padding: '24px 28px',
        marginBottom: 28,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>
            {session.proposed_household_name || 'Unknown Household'}
          </h1>
          <span style={{
            fontSize: '0.8125rem',
            fontWeight: 600,
            padding: '3px 12px',
            borderRadius: 20,
            background: sessionStatusColor(session.status) + '22',
            color: sessionStatusColor(session.status),
            textTransform: 'capitalize',
          }}>
            {session.status.replace('_', ' ')}
          </span>
        </div>

        <div style={{ marginTop: 8, fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
          {session.is_new_client === 'true' ? 'New client' : 'Existing client'} ·{' '}
          {new Date(session.created_at).toLocaleString()} ·{' '}
          {session.proposed_changes.length} proposed change{session.proposed_changes.length !== 1 ? 's' : ''}
        </div>

        {session.agent_summary && (
          <p style={{ marginTop: 12, fontSize: '0.9375rem', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
            {session.agent_summary}
          </p>
        )}

        {/* Apply button */}
        {canApply && (
          <div style={{ marginTop: 20 }}>
            <button
              onClick={handleApply}
              disabled={applying}
              style={{
                background: '#22c55e',
                color: 'white',
                border: 'none',
                borderRadius: 8,
                padding: '10px 24px',
                cursor: applying ? 'not-allowed' : 'pointer',
                fontWeight: 700,
                fontSize: '0.9375rem',
                opacity: applying ? 0.7 : 1,
                transition: 'opacity 0.15s',
              }}
            >
              {applying ? 'Applying...' : `Apply All Approved Changes (${approvedCount})`}
            </button>
          </div>
        )}

        {applyResult && (
          <div style={{
            marginTop: 14,
            padding: '10px 16px',
            background: applyResult.startsWith('Error') ? '#ef444411' : '#22c55e11',
            border: `1px solid ${applyResult.startsWith('Error') ? '#ef444433' : '#22c55e33'}`,
            borderRadius: 8,
            fontSize: '0.875rem',
            color: applyResult.startsWith('Error') ? '#ef4444' : '#22c55e',
          }}>
            {applyResult}
          </div>
        )}
      </div>

      {/* Change groups */}
      {Object.keys(groups).length === 0 ? (
        <div style={{
          padding: '40px 24px',
          textAlign: 'center',
          color: 'var(--color-text-muted)',
          background: 'var(--color-surface)',
          borderRadius: 12,
          border: '1px solid var(--color-border)',
        }}>
          No proposed changes in this session.
        </div>
      ) : (
        Object.entries(groups).map(([label, changes]) => (
          <div key={label} style={{ marginBottom: 28 }}>
            <h2 style={{
              fontSize: '1rem',
              fontWeight: 700,
              color: 'var(--color-text)',
              marginBottom: 12,
              paddingBottom: 8,
              borderBottom: '1px solid var(--color-border)',
            }}>
              {label}
              <span style={{ marginLeft: 10, fontSize: '0.8125rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>
                ({changes.length} field{changes.length !== 1 ? 's' : ''})
              </span>
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {changes.map(change => (
                <ChangeCard
                  key={change.id}
                  change={change}
                  sessionId={session.id}
                  onUpdate={handleChangeUpdate}
                />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
