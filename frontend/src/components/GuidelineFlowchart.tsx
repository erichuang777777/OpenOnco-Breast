import { useMemo } from 'react'
import type {
  GuidelineGraph,
  GuidelineNode,
  GuidelineEdge,
  TraceEntry,
} from '../api/types'

/**
 * Renders an Algorithm decision tree as a readable clinical flowchart.
 *
 * Dependency-free (no graph library): each decision step is a card with its
 * match conditions and its "if met / if not" branches, drawn as a top-down
 * flow. When a patient `trace` is supplied (or the graph already carries
 * `on_path` flags), the path the engine actually walked is highlighted —
 * turning the static guideline into a per-patient explanation of *why* a
 * recommendation was reached (CHARTER §8.3: the engine decides, this only
 * visualizes its authored logic).
 */

const ACCENT = '#1e40af'
const PATH_BG = '#eff6ff'
const PATH_BORDER = '#1e40af'

interface Props {
  graph: GuidelineGraph
  trace?: TraceEntry[]
}

const indNodeId = (id: string) => `ind:${id}`

/** Mirror of the backend overlay: mark the nodes/edges on the walked path. */
function applyTrace(graph: GuidelineGraph, trace: TraceEntry[]): GuidelineGraph {
  const pathNodes = new Set<string>(['start'])
  const pathEdges = new Set<string>()
  let prev = 'start'

  for (const entry of trace) {
    const sid = entry.step
    if (sid !== null && sid !== undefined) {
      const nodeId = `step:${sid}`
      pathNodes.add(nodeId)
      pathEdges.add(`${prev}->${nodeId}`)
      prev = nodeId
      const branch = entry.branch
      if (branch && typeof branch.result === 'string') {
        const target = indNodeId(branch.result)
        pathNodes.add(target)
        pathEdges.add(`${nodeId}->${target}`)
      }
    } else if (typeof entry.result === 'string') {
      const target = indNodeId(entry.result)
      pathNodes.add(target)
      pathEdges.add(`${prev}->${target}`)
    }
  }

  return {
    ...graph,
    nodes: graph.nodes.map((n) => ({ ...n, on_path: pathNodes.has(n.id) })),
    edges: graph.edges.map((e) => ({
      ...e,
      on_path: pathEdges.has(`${e.source}->${e.target}`),
    })),
    has_trace: true,
  }
}

function MatchLabel({ match }: { match?: string | null }) {
  if (match === 'all') return <span>All of:</span>
  if (match === 'any') return <span>Any of:</span>
  return <span>When:</span>
}

function NccnBadge({ category }: { category?: string | null }) {
  if (!category) return null
  return (
    <span
      data-testid="flowchart-nccn-badge"
      style={{
        marginLeft: 6,
        background: '#dbeafe',
        color: '#1e3a8a',
        borderRadius: 3,
        padding: '0 6px',
        fontSize: '0.72rem',
        fontWeight: 600,
      }}
    >
      NCCN {category}
    </span>
  )
}

function TargetChip({ node }: { node: GuidelineNode | undefined }) {
  if (!node) return <span style={{ color: '#9ca3af' }}>—</span>
  if (node.kind === 'decision') {
    return <span style={{ color: ACCENT }}>→ {node.label}</span>
  }
  if (node.kind === 'no_indication') {
    return <span style={{ color: '#6b7280' }}>No specific indication</span>
  }
  return (
    <span>
      <strong>{node.label}</strong>
      {node.regimen_name && (
        <span style={{ color: '#6b7280' }}> · {node.regimen_name}</span>
      )}
      <NccnBadge category={node.nccn_category} />
    </span>
  )
}

export function GuidelineFlowchart({ graph, trace }: Props) {
  const view = useMemo(
    () => (trace && trace.length ? applyTrace(graph, trace) : graph),
    [graph, trace],
  )

  const nodeById = useMemo(() => {
    const m = new Map<string, GuidelineNode>()
    view.nodes.forEach((n) => m.set(n.id, n))
    return m
  }, [view])

  const decisions = useMemo(
    () =>
      view.nodes
        .filter((n) => n.kind === 'decision')
        .sort((a, b) => Number(a.step ?? 0) - Number(b.step ?? 0)),
    [view],
  )

  const edgesFrom = (id: string, branch: 'true' | 'false'): GuidelineEdge | undefined =>
    view.edges.find((e) => e.source === id && e.branch === branch)

  const selected = view.nodes.find((n) => n.kind === 'indication' && n.on_path)

  return (
    <div data-testid="guideline-flowchart">
      <div style={{ marginBottom: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
          <strong data-testid="flowchart-algorithm-id" style={{ fontSize: '1.05rem' }}>
            {view.algorithm_id}
          </strong>
          {view.disease_id && (
            <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>{view.disease_id}</span>
          )}
          {view.line_of_therapy != null && (
            <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>
              · {view.line_of_therapy === 0 ? 'prevention' : `line ${view.line_of_therapy}`}
            </span>
          )}
          {view.has_trace && (
            <span
              data-testid="flowchart-path-legend"
              style={{
                marginLeft: 'auto',
                fontSize: '0.78rem',
                color: ACCENT,
                fontWeight: 600,
              }}
            >
              ● Path for this patient
            </span>
          )}
        </div>
        {view.purpose && (
          <p style={{ margin: '0.4rem 0 0', color: '#374151', fontSize: '0.85rem', lineHeight: 1.4 }}>
            {view.purpose}
          </p>
        )}
      </div>

      {selected && (
        <div
          data-testid="flowchart-selected-indication"
          style={{
            background: '#f0fdf4',
            border: '1px solid #16a34a',
            borderRadius: 6,
            padding: '0.5rem 0.75rem',
            marginBottom: '0.75rem',
          }}
        >
          <span style={{ color: '#15803d', fontWeight: 600 }}>Recommendation reached: </span>
          <TargetChip node={selected} />
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
        {decisions.map((node, i) => {
          const tEdge = edgesFrom(node.id, 'true')
          const fEdge = edgesFrom(node.id, 'false')
          const onPath = node.on_path
          return (
            <div key={node.id}>
              {i > 0 && (
                <div
                  aria-hidden
                  style={{ height: 10, borderLeft: '2px solid #d1d5db', marginLeft: 18 }}
                />
              )}
              <div
                data-testid={`flowchart-step-${node.step}`}
                data-on-path={onPath ? 'true' : 'false'}
                style={{
                  border: `1px solid ${onPath ? PATH_BORDER : '#e5e7eb'}`,
                  background: onPath ? PATH_BG : '#fff',
                  borderRadius: 6,
                  padding: '0.6rem 0.75rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span
                    style={{
                      background: onPath ? ACCENT : '#6b7280',
                      color: '#fff',
                      borderRadius: 4,
                      padding: '0 8px',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                    }}
                  >
                    {node.label}
                  </span>
                  {onPath && (
                    <span
                      data-testid={`flowchart-step-${node.step}-onpath`}
                      style={{ color: ACCENT, fontSize: '0.72rem', fontWeight: 600 }}
                    >
                      ● evaluated
                    </span>
                  )}
                </div>

                <div style={{ marginTop: '0.4rem', fontSize: '0.82rem', color: '#374151' }}>
                  <span style={{ color: '#6b7280' }}>
                    <MatchLabel match={node.match} />
                  </span>
                  <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.1rem' }}>
                    {node.conditions.map((c, ci) => (
                      <li key={ci} style={{ marginBottom: 2 }}>{c}</li>
                    ))}
                    {node.conditions.length === 0 && (
                      <li style={{ color: '#9ca3af' }}>(no machine-readable conditions)</li>
                    )}
                  </ul>
                </div>

                <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <div
                    data-testid={`flowchart-step-${node.step}-true`}
                    style={{
                      fontSize: '0.8rem',
                      fontWeight: tEdge?.on_path ? 600 : 400,
                      color: tEdge?.on_path ? ACCENT : '#374151',
                    }}
                  >
                    <span style={{ color: '#16a34a' }}>✓ If met</span>{' '}
                    <TargetChip node={tEdge ? nodeById.get(tEdge.target) : undefined} />
                  </div>
                  <div
                    data-testid={`flowchart-step-${node.step}-false`}
                    style={{
                      fontSize: '0.8rem',
                      fontWeight: fEdge?.on_path ? 600 : 400,
                      color: fEdge?.on_path ? ACCENT : '#374151',
                    }}
                  >
                    <span style={{ color: '#9ca3af' }}>✗ If not</span>{' '}
                    <TargetChip node={fEdge ? nodeById.get(fEdge.target) : undefined} />
                  </div>
                </div>

                {node.notes && (
                  <p style={{ margin: '0.45rem 0 0', fontSize: '0.76rem', color: '#6b7280', lineHeight: 1.4 }}>
                    {node.notes}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {view.sources.length > 0 && (
        <div data-testid="flowchart-sources" style={{ marginTop: '0.75rem', fontSize: '0.76rem', color: '#6b7280' }}>
          Sources: {view.sources.join(', ')}
        </div>
      )}
    </div>
  )
}
