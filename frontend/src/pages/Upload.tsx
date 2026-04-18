import { useCallback, useEffect, useRef, useState } from 'react'
import { uploadExcel, uploadAudio, getHouseholds } from '../api'
import type { Household, AudioInsight, UploadResult } from '../types'
import './Upload.css'

export default function Upload() {
  const [households, setHouseholds] = useState<Household[]>([])

  // Excel state
  const [excelFile, setExcelFile] = useState<File | null>(null)
  const [excelDragging, setExcelDragging] = useState(false)
  const [excelUploading, setExcelUploading] = useState(false)
  const [excelResult, setExcelResult] = useState<UploadResult | null>(null)
  const [excelError, setExcelError] = useState<string | null>(null)
  const excelInputRef = useRef<HTMLInputElement>(null)

  // Audio state
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [audioDragging, setAudioDragging] = useState(false)
  const [audioUploading, setAudioUploading] = useState(false)
  const [audioResult, setAudioResult] = useState<AudioInsight | null>(null)
  const [audioError, setAudioError] = useState<string | null>(null)
  const [selectedHousehold, setSelectedHousehold] = useState<string>('')
  const audioInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getHouseholds()
      .then(r => setHouseholds(r.data))
      .catch(() => {})
  }, [])

  // --- Excel ---
  const handleExcelDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setExcelDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && isExcelFile(file)) {
      setExcelFile(file)
      setExcelResult(null)
      setExcelError(null)
    } else {
      setExcelError('Please upload a .csv, .xlsx, or .xls file.')
    }
  }, [])

  const handleExcelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setExcelFile(file)
      setExcelResult(null)
      setExcelError(null)
    }
  }

  const handleExcelUpload = async () => {
    if (!excelFile) return
    setExcelUploading(true)
    setExcelError(null)
    try {
      const res = await uploadExcel(excelFile)
      setExcelResult(res.data)
      setExcelFile(null)
      if (excelInputRef.current) excelInputRef.current.value = ''
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setExcelError(msg || 'Upload failed. Please check the file format.')
    } finally {
      setExcelUploading(false)
    }
  }

  // --- Audio ---
  const handleAudioDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setAudioDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && isAudioFile(file)) {
      setAudioFile(file)
      setAudioResult(null)
      setAudioError(null)
    } else {
      setAudioError('Please upload a .mp3, .wav, or .m4a file.')
    }
  }, [])

  const handleAudioChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setAudioFile(file)
      setAudioResult(null)
      setAudioError(null)
    }
  }

  const handleAudioUpload = async () => {
    if (!audioFile) return
    setAudioUploading(true)
    setAudioError(null)
    try {
      const hhId = selectedHousehold ? parseInt(selectedHousehold, 10) : undefined
      const res = await uploadAudio(audioFile, hhId)
      setAudioResult(res.data)
      setAudioFile(null)
      if (audioInputRef.current) audioInputRef.current.value = ''
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setAudioError(msg || 'Audio upload failed. Please try again.')
    } finally {
      setAudioUploading(false)
    }
  }

  return (
    <div className="page-wrapper">
      <div className="page-header">
        <h1 className="page-title">Upload</h1>
        <p className="page-subtitle">Import client data via spreadsheet or transcribe meeting recordings</p>
      </div>

      <div className="upload-grid">

        {/* === Excel Upload === */}
        <div className="card card-padded upload-section">
          <div className="upload-section-header">
            <div className="upload-section-icon upload-section-icon-excel">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <polyline points="10 9 9 9 8 9"/>
              </svg>
            </div>
            <div>
              <h2 className="upload-section-title">Excel / CSV Import</h2>
              <p className="upload-section-sub">Upload a spreadsheet to import household data</p>
            </div>
          </div>

          {/* Drop Zone */}
          <div
            className={`dropzone${excelDragging ? ' dropzone-active' : ''}${excelFile ? ' dropzone-has-file' : ''}`}
            onDragOver={e => { e.preventDefault(); setExcelDragging(true) }}
            onDragLeave={() => setExcelDragging(false)}
            onDrop={handleExcelDrop}
            onClick={() => excelInputRef.current?.click()}
          >
            <input
              ref={excelInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="dropzone-input"
              onChange={handleExcelChange}
            />
            {excelFile ? (
              <div className="dropzone-file-info">
                <div className="dropzone-file-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                </div>
                <div>
                  <p className="dropzone-file-name">{excelFile.name}</p>
                  <p className="dropzone-file-size">{formatBytes(excelFile.size)}</p>
                </div>
                <button
                  className="dropzone-remove"
                  onClick={e => { e.stopPropagation(); setExcelFile(null) }}
                  title="Remove"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            ) : (
              <div className="dropzone-empty">
                <div className="dropzone-upload-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="16 16 12 12 8 16"/>
                    <line x1="12" y1="12" x2="12" y2="21"/>
                    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
                  </svg>
                </div>
                <p className="dropzone-title">Drop your file here</p>
                <p className="dropzone-sub">or <span className="dropzone-link">click to browse</span></p>
                <p className="dropzone-formats">Supports .csv, .xlsx, .xls</p>
              </div>
            )}
          </div>

          {excelError && (
            <div className="error-message" style={{ marginTop: 12 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {excelError}
            </div>
          )}

          <button
            className="btn btn-primary"
            style={{ marginTop: 16, width: '100%', justifyContent: 'center' }}
            onClick={handleExcelUpload}
            disabled={!excelFile || excelUploading}
          >
            {excelUploading ? (
              <><div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} />Processing…</>
            ) : (
              <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>Upload & Import</>
            )}
          </button>

          {/* Excel Result */}
          {excelResult && (
            <div className="upload-result-box">
              <div className="upload-result-header">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Import Complete
              </div>
              <div className="upload-result-stats">
                {excelResult.created !== undefined && (
                  <div className="upload-result-stat">
                    <span className="upload-result-stat-value">{excelResult.created}</span>
                    <span className="upload-result-stat-label">Households Created</span>
                  </div>
                )}
                {excelResult.updated !== undefined && (
                  <div className="upload-result-stat">
                    <span className="upload-result-stat-value">{excelResult.updated}</span>
                    <span className="upload-result-stat-label">Households Updated</span>
                  </div>
                )}
              </div>
              {excelResult.message && (
                <p className="upload-result-message">{excelResult.message}</p>
              )}
              {excelResult.errors && excelResult.errors.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <p className="upload-preview-label" style={{ color: 'var(--color-error)' }}>Errors</p>
                  <ul style={{ margin: 0, paddingLeft: 16, fontSize: '0.85rem', color: 'var(--color-error)' }}>
                    {excelResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* === Audio Upload === */}
        <div className="card card-padded upload-section">
          <div className="upload-section-header">
            <div className="upload-section-icon upload-section-icon-audio">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            </div>
            <div>
              <h2 className="upload-section-title">Audio Transcription</h2>
              <p className="upload-section-sub">Upload a recording to extract insights and action items</p>
            </div>
          </div>

          {/* Household Selector */}
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="form-label">Link to Household (optional)</label>
            <select
              className="form-input form-select"
              value={selectedHousehold}
              onChange={e => setSelectedHousehold(e.target.value)}
            >
              <option value="">— Select household —</option>
              {households.map(h => (
                <option key={h.id} value={h.id}>{h.name}</option>
              ))}
            </select>
          </div>

          {/* Drop Zone */}
          <div
            className={`dropzone dropzone-audio${audioDragging ? ' dropzone-active' : ''}${audioFile ? ' dropzone-has-file' : ''}`}
            onDragOver={e => { e.preventDefault(); setAudioDragging(true) }}
            onDragLeave={() => setAudioDragging(false)}
            onDrop={handleAudioDrop}
            onClick={() => audioInputRef.current?.click()}
          >
            <input
              ref={audioInputRef}
              type="file"
              accept=".mp3,.wav,.m4a"
              className="dropzone-input"
              onChange={handleAudioChange}
            />
            {audioFile ? (
              <div className="dropzone-file-info">
                <div className="dropzone-file-icon dropzone-file-icon-audio">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 18V5l12-2v13"/>
                    <circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
                  </svg>
                </div>
                <div>
                  <p className="dropzone-file-name">{audioFile.name}</p>
                  <p className="dropzone-file-size">{formatBytes(audioFile.size)}</p>
                </div>
                <button
                  className="dropzone-remove"
                  onClick={e => { e.stopPropagation(); setAudioFile(null) }}
                  title="Remove"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            ) : (
              <div className="dropzone-empty">
                <div className="dropzone-upload-icon dropzone-upload-icon-audio">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                  </svg>
                </div>
                <p className="dropzone-title">Drop your audio file here</p>
                <p className="dropzone-sub">or <span className="dropzone-link">click to browse</span></p>
                <p className="dropzone-formats">Supports .mp3, .wav, .m4a</p>
              </div>
            )}
          </div>

          {audioError && (
            <div className="error-message" style={{ marginTop: 12 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              {audioError}
            </div>
          )}

          <button
            className="btn btn-primary"
            style={{ marginTop: 16, width: '100%', justifyContent: 'center', background: 'linear-gradient(135deg, #7c3aed, #2563eb)' }}
            onClick={handleAudioUpload}
            disabled={!audioFile || audioUploading}
          >
            {audioUploading ? (
              <><div className="spinner spinner-sm" style={{ borderTopColor: 'white' }} />Transcribing…</>
            ) : (
              <><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg>Upload & Transcribe</>
            )}
          </button>

          {/* Audio Result */}
          {audioResult && (
            <div className="upload-result-box upload-result-audio">
              <div className="upload-result-header upload-result-header-audio">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Transcription Complete
              </div>

              {audioResult.transcription && (
                <div className="audio-result-block">
                  <h5 className="audio-result-label">Transcription</h5>
                  <div className="audio-transcription-box">
                    <p>{audioResult.transcription}</p>
                  </div>
                </div>
              )}

              {audioResult.extracted_data?.key_insights && audioResult.extracted_data.key_insights.length > 0 && (
                <div className="audio-result-block">
                  <h5 className="audio-result-label">Key Insights</h5>
                  <ul className="audio-insights-list">
                    {audioResult.extracted_data.key_insights.map((ins, i) => (
                      <li key={i}>
                        <span className="audio-insight-bullet" />
                        {ins}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {audioResult.extracted_data?.action_items && audioResult.extracted_data.action_items.length > 0 && (
                <div className="audio-result-block">
                  <h5 className="audio-result-label">Action Items</h5>
                  <ul className="audio-action-list">
                    {audioResult.extracted_data.action_items.map((item, i) => (
                      <li key={i}>
                        <input type="checkbox" id={`upload-action-${i}`} />
                        <label htmlFor={`upload-action-${i}`}>{item}</label>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function isExcelFile(file: File): boolean {
  return /\.(csv|xlsx|xls)$/i.test(file.name)
}

function isAudioFile(file: File): boolean {
  return /\.(mp3|wav|m4a)$/i.test(file.name)
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
