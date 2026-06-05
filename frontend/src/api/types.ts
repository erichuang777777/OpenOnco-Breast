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
  his_sync_status?: string
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
  body_json?: Record<string, unknown>
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
