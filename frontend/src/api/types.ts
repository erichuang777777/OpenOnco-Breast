// Auto-generated types aligned with backend OpenAPI schema

export interface PatientResponse {
  mrn: string
  masked_name: string
  sex?: string
  dob_year?: number
  disease_summary?: string
  status: string
  primary_doctor_id?: string
  his_patient_id?: string
  his_synced_at?: string
  created_at: string
  updated_at: string
  care_team: CareTeamMemberResponse[]
  urgent_reminder_count?: number
}

export interface CareTeamMemberResponse {
  id: string
  patient_mrn: string
  user_id: string
  member_role: string
  specialty?: string
  assigned_by: string
  assigned_at: string
}

export interface ReminderResponse {
  id: string
  patient_mrn: string
  reminder_type: string
  urgency: string
  title: string
  detail?: string
  due_date: string
  status: string
  triggered_by: string
  acknowledged_by?: string
  acknowledged_at?: string
  created_at: string
}

export interface TimelineEventResponse {
  id: string
  patient_mrn: string
  event_type: string
  event_time: string
  source: string
  title: string
  body_json?: unknown
  created_by?: string
  created_at: string
}

export interface ConsultationResponse {
  id: string
  patient_mrn: string
  from_user_id: string
  to_user_id: string
  subject: string
  status: string
  created_at: string
  updated_at: string
  messages: ConsultationMessageResponse[]
}

export interface ConsultationMessageResponse {
  id: string
  consultation_id: string
  sender_id: string
  body: string
  created_at: string
}

export interface MtdSessionResponse {
  id: string
  meeting_date: string
  location?: string
  created_by: string
  status: string
  created_at: string
  cases: MtdCaseResponse[]
}

export interface MtdCaseResponse {
  id: string
  mtd_session_id: string
  patient_mrn: string
  added_by: string
  reason?: string
  status: string
  conclusion_text?: string
  conclusion_by?: string
  conclusion_at?: string
  created_at: string
}

// ── Guideline flowchart visualization ─────────────────────────────────────────

export interface GuidelineNode {
  id: string
  kind: 'start' | 'decision' | 'indication' | 'no_indication'
  label: string
  step?: number | string | null
  match?: 'all' | 'any' | 'single' | null
  conditions: string[]
  red_flags: string[]
  notes?: string | null
  indication_id?: string | null
  regimen_name?: string | null
  nccn_category?: string | null
  evidence_level?: string | null
  on_path: boolean
}

export interface GuidelineEdge {
  source: string
  target: string
  branch?: 'true' | 'false' | null
  label?: string | null
  on_path: boolean
}

export interface GuidelineGraph {
  algorithm_id: string
  disease_id?: string | null
  line_of_therapy?: number | string | null
  purpose?: string | null
  default_indication?: string | null
  alternative_indication?: string | null
  sources: string[]
  nodes: GuidelineNode[]
  edges: GuidelineEdge[]
  has_trace: boolean
}

export interface GuidelineSummary {
  algorithm_id: string
  disease_id?: string | null
  line_of_therapy?: number | string | null
  purpose?: string | null
}

// One entry of the engine decision-tree trace (PlanResponse.trace).
export interface TraceEntry {
  step?: number | string | null
  outcome?: boolean
  branch?: { result?: string | boolean | null; next_step?: number | string } | null
  result?: string | null
  fired_red_flags?: string[]
  winner_red_flag?: string | null
}
