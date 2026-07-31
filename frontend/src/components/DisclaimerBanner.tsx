/**
 * Medical disclaimer. OpenOnco is an informational decision-SUPPORT tool, not
 * a medical device and not an autonomous decision-maker (CHARTER §11 + §15;
 * §8.3). The HCP must verify every recommendation. Surfacing this in the UI —
 * especially where treatment recommendations appear — is an automation-bias
 * mitigation required by the FDA non-device CDS positioning.
 */

export function DisclaimerBanner({ variant = 'compact' }: { variant?: 'compact' | 'prominent' }) {
  if (variant === 'prominent') {
    return (
      <div
        data-testid="disclaimer-prominent"
        role="note"
        style={{
          background: '#fffbeb',
          border: '1px solid #f59e0b',
          borderRadius: 6,
          padding: '0.75rem 1rem',
          marginBottom: '1rem',
          fontSize: '0.85rem',
          color: '#78350f',
          lineHeight: 1.5,
        }}
      >
        <strong>⚠️ 臨床決策支援 · 非醫療器材</strong>
        <div style={{ marginTop: 4 }}>
          本系統提供之治療建議僅供腫瘤多專科團隊（MDT）討論參考，由規則引擎依
          versioned 知識庫產生，<strong>並非由 AI 自主決策</strong>（CHARTER §8.3）。
          所有建議<strong>必須由具完整臨床資訊的主治腫瘤科醫師核實</strong>後方可採用。
          This is an informational decision-support tool, not a medical device;
          every recommendation must be verified by the treating oncologist.
        </div>
      </div>
    )
  }
  return (
    <div
      data-testid="disclaimer-compact"
      role="note"
      style={{
        background: '#f8fafc',
        borderBottom: '1px solid #e2e8f0',
        padding: '0.25rem 1rem',
        fontSize: '0.72rem',
        color: '#64748b',
        textAlign: 'center',
      }}
    >
      OpenOnco 為臨床決策支援工具（非醫療器材）；所有建議須由主治醫師核實。
      Informational support only — not a medical device. Verify every recommendation.
    </div>
  )
}
