import { useState, useEffect } from 'react'
import type { GuidelineGraph, GuidelineSummary } from '../api/types'
import { GuidelineFlowchart } from '../components/GuidelineFlowchart'

/**
 * Guideline browser: pick a disease, list its algorithms, and visualize any
 * one as a flowchart. Read-only — the same decision trees the engine walks,
 * made inspectable for clinicians and reviewers.
 */
export function GuidelinesPage() {
  const [disease, setDisease] = useState('DIS-BREAST')
  const [algorithms, setAlgorithms] = useState<GuidelineSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [graph, setGraph] = useState<GuidelineGraph | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch(`/api/v1/guidelines?disease=${encodeURIComponent(disease)}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : { algorithms: [] }))
      .then((data) => setAlgorithms(data.algorithms ?? []))
      .catch(() => setAlgorithms([]))
  }, [disease])

  useEffect(() => {
    if (!selectedId) {
      setGraph(null)
      return
    }
    setLoading(true)
    fetch(`/api/v1/guidelines/${encodeURIComponent(selectedId)}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setGraph(data))
      .catch(() => setGraph(null))
      .finally(() => setLoading(false))
  }, [selectedId])

  return (
    <div data-testid="guidelines-page" style={{ padding: '1rem', maxWidth: 1100, margin: '0 auto' }}>
      <h1>指引流程圖 · Guideline Flowcharts</h1>

      <div style={{ marginBottom: '1rem' }}>
        <label style={{ marginRight: '0.5rem' }}>疾病 Disease:</label>
        <input
          data-testid="guidelines-disease-input"
          value={disease}
          onChange={(e) => {
            setDisease(e.target.value)
            setSelectedId(null)
          }}
          style={{ padding: '0.25rem 0.5rem' }}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1rem', alignItems: 'start' }}>
        <div data-testid="guidelines-list" style={{ border: '1px solid #e5e7eb', borderRadius: 6, overflow: 'hidden' }}>
          {algorithms.length === 0 && (
            <div data-testid="guidelines-empty" style={{ padding: '0.75rem', color: '#6b7280' }}>
              此疾病無演算法 No algorithms for this disease.
            </div>
          )}
          {algorithms.map((a) => (
            <button
              key={a.algorithm_id}
              data-testid={`guideline-item-${a.algorithm_id}`}
              onClick={() => setSelectedId(a.algorithm_id)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '0.6rem 0.75rem',
                border: 'none',
                borderBottom: '1px solid #f1f5f9',
                background: selectedId === a.algorithm_id ? '#eff6ff' : '#fff',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{a.algorithm_id}</div>
              {a.line_of_therapy != null && (
                <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                  {a.line_of_therapy === 0 ? 'prevention' : `line ${a.line_of_therapy}`}
                </div>
              )}
            </button>
          ))}
        </div>

        <div style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: '1rem', minHeight: 200 }}>
          {loading && <div data-testid="guidelines-loading">載入中…</div>}
          {!loading && !graph && (
            <div data-testid="guidelines-placeholder" style={{ color: '#9ca3af' }}>
              ← 選擇演算法以檢視流程圖 Select an algorithm to view its flowchart.
            </div>
          )}
          {!loading && graph && <GuidelineFlowchart graph={graph} />}
        </div>
      </div>
    </div>
  )
}
