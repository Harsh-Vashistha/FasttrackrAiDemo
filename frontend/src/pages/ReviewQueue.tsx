import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ReviewSession } from '../types'
import client from '../api'

function statusColor(status: string): string {
  switch (status) {
    case 'completed': return '#22c55e'
    case 'pending': return '#f59e0b'
    case 'in_review': return '#3b82f6'
    case 'dismissed': return '#6b7280'
    default: return '#6b7280'
  }
}

export default function ReviewQueue() {
  const [sessions, setSessions] = useState<ReviewSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    client.get<ReviewSession[]>('/review')
      .then(r => setSessions(r.data))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
        Loading review queue...
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: '48px 24px', textAlign: 'center', color: '#ef4444' }}>
        Failed to load review queue: {error}
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text)', margin: 0 }}>
          Review Queue
        </h1>
        <p style={{ marginTop: 8, color: 'var(--color-text-muted)', fontSize: '0.9375rem' }}>
          Review and approve AI-proposed changes before they are written to the database.
        </p>
      </div>

      {sessions.length === 0 ? (
        <div style={{
          padding: '64px 24px',
          textAlign: 'center',
          background: 'var(--color-surface)',
          borderRadius: 12,
          border: '1px solid var(--color-border)',
          color: 'var(--color-text-muted)',
        }}>
          <div style={{ fontSize: '2.5rem', marginBottom: 16 }}>📋</div>
          <div style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: 8, color: 'var(--color-text)' }}>
            No pending reviews
          </div>
          <div style={{ fontSize: '0.9375rem' }}>
            Upload an audio file to generate a review session.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {sessions.map(session => (
            <div
              key={session.id}
              onClick={() => navigate(`/review/${session.id}`)}
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 12,
                padding: '20px 24px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-accent)'
                ;(e.currentTarget as HTMLDivElement).style.boxShadow = '0 4px 20px rgba(37,99,235,0.1)'
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-border)'
                ;(e.currentTarget as HTMLDivElement).style.boxShadow = 'none'
              }}
            >
              {/* Header row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--color-text)' }}>
                    {session.proposed_household_name || 'Unknown Household'}
                  </span>
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    padding: '2px 10px',
                    borderRadius: 20,
                    background: statusColor(session.status) + '22',
                    color: statusColor(session.status),
                    textTransform: 'capitalize',
                  }}>
                    {session.status.replace('_', ' ')}
                  </span>
                </div>
                <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                  {new Date(session.created_at).toLocaleString()}
                </span>
              </div>

              {/* Summary */}
              {session.agent_summary && (
                <p style={{
                  marginTop: 10,
                  fontSize: '0.9rem',
                  color: 'var(--color-text-muted)',
                  lineHeight: 1.5,
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}>
                  {session.agent_summary}
                </p>
              )}

              {/* Change counts */}
              <div style={{ display: 'flex', gap: 16, marginTop: 14, flexWrap: 'wrap' }}>
                {(session.pending_count ?? 0) > 0 && (
                  <Pill label="pending" count={session.pending_count!} color="#f59e0b" />
                )}
                {(session.approved_count ?? 0) > 0 && (
                  <Pill label="approved" count={session.approved_count!} color="#22c55e" />
                )}
                {(session.revised_count ?? 0) > 0 && (
                  <Pill label="revised" count={session.revised_count!} color="#3b82f6" />
                )}
                {(session.dismissed_count ?? 0) > 0 && (
                  <Pill label="dismissed" count={session.dismissed_count!} color="#6b7280" />
                )}
                {(session.rejected_count ?? 0) > 0 && (
                  <Pill label="rejected" count={session.rejected_count!} color="#ef4444" />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Pill({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <span style={{
      fontSize: '0.8125rem',
      fontWeight: 500,
      color,
      background: color + '18',
      padding: '3px 10px',
      borderRadius: 20,
    }}>
      {count} {label}
    </span>
  )
}
