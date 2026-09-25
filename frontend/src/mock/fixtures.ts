/**
 * Demo fixtures — realistic fake clinical data for UI development.
 * All names / MRNs are fictional. No real patient data.
 */

import type {
  PatientResponse,
  CareTeamMemberResponse,
  ReminderResponse,
  TimelineEventResponse,
  ConsultationResponse,
  MtdSessionResponse,
} from '../api/types'

// ─────────────────────────────────────────────────────────────────────────────
// Users
// ─────────────────────────────────────────────────────────────────────────────

export interface MockUser {
  id: string
  email: string
  display_name: string
  role: string
  specialty?: string
  avatar_initials: string
}

export const MOCK_USERS: MockUser[] = [
  {
    id: 'dr-001',
    email: 'lin.zhiming@hospital.tw',
    display_name: '林志明 醫師',
    role: 'tumor_board_hcp',
    specialty: '腫瘤內科',
    avatar_initials: '林',
  },
  {
    id: 'dr-002',
    email: 'chen.jianzhi@hospital.tw',
    display_name: '陳建志 醫師',
    role: 'tumor_board_hcp',
    specialty: '乳房外科',
    avatar_initials: '陳',
  },
  {
    id: 'dr-003',
    email: 'huang.sufang@hospital.tw',
    display_name: '黃素芳 醫師',
    role: 'clinic_hcp',
    specialty: '放射腫瘤科',
    avatar_initials: '黃',
  },
  {
    id: 'coord-001',
    email: 'zhao.xiuying@hospital.tw',
    display_name: '趙秀英 個管師',
    role: 'clinic_hcp',
    specialty: '腫瘤個案管理',
    avatar_initials: '趙',
  },
  {
    id: 'nurse-001',
    email: 'wu.lizhen@hospital.tw',
    display_name: '吳麗珍 護理師',
    role: 'clinic_hcp',
    specialty: '腫瘤科護理',
    avatar_initials: '吳',
  },
]

// Currently logged-in demo user
export const MOCK_ME: MockUser & { sub: string } = {
  ...MOCK_USERS[0],
  sub: 'dr-001',
}

// ─────────────────────────────────────────────────────────────────────────────
// Care teams
// ─────────────────────────────────────────────────────────────────────────────

function makeCareTeam(mrn: string, members: Array<{ user_id: string; role: string }>): CareTeamMemberResponse[] {
  return members.map((m, i) => ({
    id: `ct-${mrn}-${i}`,
    patient_mrn: mrn,
    user_id: m.user_id,
    member_role: m.role,
    specialty: MOCK_USERS.find(u => u.id === m.user_id)?.specialty,
    assigned_by: 'dr-001',
    assigned_at: '2026-01-10T08:00:00Z',
  }))
}

// ─────────────────────────────────────────────────────────────────────────────
// Patients
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_PATIENTS: PatientResponse[] = [
  {
    mrn: 'MRN-001',
    masked_name: '王●●',
    sex: 'F',
    dob_year: 1971,
    disease_summary: '乳癌 HER2+ · 第四期 · 骨轉移',
    status: 'active',
    primary_doctor_id: 'dr-001',
    his_patient_id: 'HIS-10421',
    his_synced_at: '2026-06-04T07:30:00Z',
    his_sync_status: 'ok',
    created_at: '2026-01-15T08:00:00Z',
    updated_at: '2026-06-04T07:30:00Z',
    care_team: makeCareTeam('MRN-001', [
      { user_id: 'dr-001', role: 'primary_hcp' },
      { user_id: 'dr-002', role: 'surgeon' },
      { user_id: 'coord-001', role: 'care_coordinator' },
    ]),
    urgent_reminder_count: 2,
  },
  {
    mrn: 'MRN-002',
    masked_name: '李●●',
    sex: 'F',
    dob_year: 1968,
    disease_summary: '乳癌 ER+/PR+ HER2- · 第三期 · 術後輔助治療中',
    status: 'active',
    primary_doctor_id: 'dr-001',
    his_patient_id: 'HIS-10356',
    his_synced_at: '2026-06-03T14:00:00Z',
    his_sync_status: 'ok',
    created_at: '2026-02-01T09:00:00Z',
    updated_at: '2026-06-03T14:00:00Z',
    care_team: makeCareTeam('MRN-002', [
      { user_id: 'dr-001', role: 'primary_hcp' },
      { user_id: 'dr-003', role: 'radiation_oncologist' },
      { user_id: 'nurse-001', role: 'oncology_nurse' },
    ]),
    urgent_reminder_count: 1,
  },
  {
    mrn: 'MRN-003',
    masked_name: '陳●●',
    sex: 'F',
    dob_year: 1985,
    disease_summary: '乳癌 TNBC · 第二期 · 新輔助化療後手術',
    status: 'active',
    primary_doctor_id: 'dr-002',
    his_patient_id: undefined,
    his_synced_at: undefined,
    his_sync_status: 'never',
    created_at: '2026-03-10T10:00:00Z',
    updated_at: '2026-05-28T11:00:00Z',
    care_team: makeCareTeam('MRN-003', [
      { user_id: 'dr-002', role: 'primary_hcp' },
      { user_id: 'dr-001', role: 'medical_oncologist' },
    ]),
    urgent_reminder_count: 0,
  },
  {
    mrn: 'MRN-004',
    masked_name: '張●●',
    sex: 'F',
    dob_year: 1978,
    disease_summary: '乳癌 BRCA1+ · 一期 · 預防性手術評估中',
    status: 'active',
    primary_doctor_id: 'dr-001',
    his_patient_id: 'HIS-10489',
    his_synced_at: '2026-05-31T09:00:00Z',
    his_sync_status: 'stale',
    created_at: '2026-04-05T08:00:00Z',
    updated_at: '2026-05-31T09:00:00Z',
    care_team: makeCareTeam('MRN-004', [
      { user_id: 'dr-001', role: 'primary_hcp' },
      { user_id: 'coord-001', role: 'care_coordinator' },
    ]),
    urgent_reminder_count: 1,
  },
  {
    mrn: 'MRN-005',
    masked_name: '林●●',
    sex: 'F',
    dob_year: 1963,
    disease_summary: '乳癌 ER+ · 轉移性 · 第二線化療',
    status: 'active',
    primary_doctor_id: 'dr-003',
    his_patient_id: undefined,
    his_synced_at: undefined,
    his_sync_status: 'never',
    created_at: '2026-01-20T11:00:00Z',
    updated_at: '2026-06-01T10:00:00Z',
    care_team: makeCareTeam('MRN-005', [
      { user_id: 'dr-003', role: 'primary_hcp' },
      { user_id: 'dr-001', role: 'medical_oncologist' },
      { user_id: 'nurse-001', role: 'oncology_nurse' },
    ]),
    urgent_reminder_count: 0,
  },
]

export const MOCK_STATS = { total: 5, urgent: 3, followup: 2, mtd: 2 }

// ─────────────────────────────────────────────────────────────────────────────
// Timelines (per patient)
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_TIMELINES: Record<string, TimelineEventResponse[]> = {
  'MRN-001': [
    {
      id: 'tl-001-06', patient_mrn: 'MRN-001',
      event_type: 'doctor_note', event_time: '2026-06-04T10:30:00Z',
      source: 'manual', title: '本次門診：骨轉移疼痛控制良好，繼續 pertuzumab + trastuzumab + docetaxel',
      body_json: {}, created_by: 'dr-001', created_at: '2026-06-04T10:30:00Z',
    },
    {
      id: 'tl-001-05', patient_mrn: 'MRN-001',
      event_type: 'onco_query_initiated', event_time: '2026-06-03T09:00:00Z',
      source: 'system_rule', title: 'OpenOnco 分析已啟動',
      body_json: { plan_id: 'plan-001' }, created_by: 'dr-001', created_at: '2026-06-03T09:00:00Z',
    },
    {
      id: 'tl-001-04', patient_mrn: 'MRN-001',
      event_type: 'his_sync', event_time: '2026-06-04T07:30:00Z',
      source: 'his_sync', title: 'HIS 同步：CBC 白血球 3.8，Hb 9.2（輕度貧血）',
      body_json: {}, created_at: '2026-06-04T07:30:00Z',
    },
    {
      id: 'tl-001-03', patient_mrn: 'MRN-001',
      event_type: 'mtd_conclusion', event_time: '2026-05-28T14:00:00Z',
      source: 'system_rule', title: '腫瘤委員會結論：維持現行治療方案，4 週後重新評估骨轉移反應',
      body_json: {}, created_at: '2026-05-28T14:00:00Z',
    },
    {
      id: 'tl-001-02', patient_mrn: 'MRN-001',
      event_type: 'consultation_reply', event_time: '2026-05-20T11:00:00Z',
      source: 'manual', title: '陳建志 醫師回覆諮詢：建議骨科會診評估脊椎穩定性',
      body_json: {}, created_at: '2026-05-20T11:00:00Z',
    },
    {
      id: 'tl-001-01', patient_mrn: 'MRN-001',
      event_type: 'coordinator_note', event_time: '2026-05-15T09:00:00Z',
      source: 'manual', title: '趙秀英 個管師：已協助病患申請重大傷病卡',
      body_json: {}, created_by: 'coord-001', created_at: '2026-05-15T09:00:00Z',
    },
  ],

  'MRN-002': [
    {
      id: 'tl-002-04', patient_mrn: 'MRN-002',
      event_type: 'doctor_note', event_time: '2026-06-03T14:00:00Z',
      source: 'manual', title: '術後輔助化療第 4 週期，副作用輕微，繼續 AC-T 方案',
      body_json: {}, created_by: 'dr-001', created_at: '2026-06-03T14:00:00Z',
    },
    {
      id: 'tl-002-03', patient_mrn: 'MRN-002',
      event_type: 'his_sync', event_time: '2026-06-03T14:00:00Z',
      source: 'his_sync', title: 'HIS 同步：ECHO 射出分率 62%（正常）',
      body_json: {}, created_at: '2026-06-03T14:00:00Z',
    },
    {
      id: 'tl-002-02', patient_mrn: 'MRN-002',
      event_type: 'onco_query_initiated', event_time: '2026-05-10T10:00:00Z',
      source: 'system_rule', title: 'OpenOnco 分析已啟動',
      body_json: { plan_id: 'plan-002' }, created_by: 'dr-001', created_at: '2026-05-10T10:00:00Z',
    },
    {
      id: 'tl-002-01', patient_mrn: 'MRN-002',
      event_type: 'coordinator_note', event_time: '2026-05-01T09:00:00Z',
      source: 'manual', title: '完成放射治療計畫說明，病患同意進行輔助放療',
      body_json: {}, created_by: 'coord-001', created_at: '2026-05-01T09:00:00Z',
    },
  ],

  'MRN-003': [
    {
      id: 'tl-003-03', patient_mrn: 'MRN-003',
      event_type: 'doctor_note', event_time: '2026-05-28T11:00:00Z',
      source: 'manual', title: '術後病理報告：pCR（完全病理緩解），無殘存腫瘤',
      body_json: {}, created_by: 'dr-002', created_at: '2026-05-28T11:00:00Z',
    },
    {
      id: 'tl-003-02', patient_mrn: 'MRN-003',
      event_type: 'onco_query_initiated', event_time: '2026-04-01T09:00:00Z',
      source: 'system_rule', title: 'OpenOnco 分析已啟動',
      body_json: { plan_id: 'plan-003' }, created_by: 'dr-002', created_at: '2026-04-01T09:00:00Z',
    },
    {
      id: 'tl-003-01', patient_mrn: 'MRN-003',
      event_type: 'coordinator_note', event_time: '2026-03-15T10:00:00Z',
      source: 'manual', title: '新輔助化療同意書簽署完成，排程 carboplatin + paclitaxel',
      body_json: {}, created_by: 'nurse-001', created_at: '2026-03-15T10:00:00Z',
    },
  ],

  'MRN-004': [
    {
      id: 'tl-004-02', patient_mrn: 'MRN-004',
      event_type: 'doctor_note', event_time: '2026-05-31T09:00:00Z',
      source: 'manual', title: 'BRCA1 胚系突變確認陽性，與病患討論預防性雙側乳房切除術選項',
      body_json: {}, created_by: 'dr-001', created_at: '2026-05-31T09:00:00Z',
    },
    {
      id: 'tl-004-01', patient_mrn: 'MRN-004',
      event_type: 'onco_query_initiated', event_time: '2026-05-20T10:00:00Z',
      source: 'system_rule', title: 'OpenOnco 分析已啟動',
      body_json: { plan_id: 'plan-004' }, created_by: 'dr-001', created_at: '2026-05-20T10:00:00Z',
    },
  ],

  'MRN-005': [
    {
      id: 'tl-005-03', patient_mrn: 'MRN-005',
      event_type: 'doctor_note', event_time: '2026-06-01T10:00:00Z',
      source: 'manual', title: '第一線內分泌治療疾病進展，評估換用 fulvestrant + CDK4/6 抑制劑',
      body_json: {}, created_by: 'dr-003', created_at: '2026-06-01T10:00:00Z',
    },
    {
      id: 'tl-005-02', patient_mrn: 'MRN-005',
      event_type: 'onco_query_initiated', event_time: '2026-05-25T09:00:00Z',
      source: 'system_rule', title: 'OpenOnco 分析已啟動',
      body_json: { plan_id: 'plan-005' }, created_by: 'dr-003', created_at: '2026-05-25T09:00:00Z',
    },
    {
      id: 'tl-005-01', patient_mrn: 'MRN-005',
      event_type: 'alert', event_time: '2026-05-20T08:00:00Z',
      source: 'system_rule', title: '⚠ ESR1 突變偵測陽性 — 建議考慮換用不受 ESR1 影響的治療',
      body_json: {}, created_at: '2026-05-20T08:00:00Z',
    },
  ],
}

// ─────────────────────────────────────────────────────────────────────────────
// Reminders (per patient)
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_REMINDERS: Record<string, ReminderResponse[]> = {
  'MRN-001': [
    {
      id: 'rem-001-01', patient_mrn: 'MRN-001',
      reminder_type: 'drug_reapplication', urgency: 'high',
      title: '須在 6/10 前重新申請 pertuzumab 健保給付',
      detail: '本次核准批次已到期，逾期未申請將停藥',
      due_date: '2026-06-10T00:00:00Z', status: 'active',
      triggered_by: 'rule:drug_reapplication', acknowledged_by: undefined, acknowledged_at: undefined,
      created_at: '2026-06-01T08:00:00Z',
    },
    {
      id: 'rem-001-02', patient_mrn: 'MRN-001',
      reminder_type: 'imaging_due', urgency: 'high',
      title: 'CT 影像追蹤逾期（原排 5/25）',
      detail: '骨轉移監測影像已延誤 10 天，需盡速安排',
      due_date: '2026-05-25T00:00:00Z', status: 'active',
      triggered_by: 'rule:imaging_overdue', acknowledged_by: undefined, acknowledged_at: undefined,
      created_at: '2026-05-26T08:00:00Z',
    },
  ],
  'MRN-002': [
    {
      id: 'rem-002-01', patient_mrn: 'MRN-002',
      reminder_type: 'cardiac_monitoring', urgency: 'normal',
      title: '心臟毒性追蹤：第 4 週期前需複查 ECHO',
      detail: '依 AC-T 方案監測心臟功能',
      due_date: '2026-06-15T00:00:00Z', status: 'active',
      triggered_by: 'rule:cardiac_monitoring', acknowledged_by: undefined, acknowledged_at: undefined,
      created_at: '2026-06-01T08:00:00Z',
    },
  ],
  'MRN-004': [
    {
      id: 'rem-004-01', patient_mrn: 'MRN-004',
      reminder_type: 'brca_followup', urgency: 'high',
      title: 'BRCA1 陽性 — 需安排遺傳諮詢',
      detail: '確認突變後 4 週內需完成遺傳諮詢，協助病患決策',
      due_date: '2026-06-28T00:00:00Z', status: 'active',
      triggered_by: 'rule:brca_followup', acknowledged_by: undefined, acknowledged_at: undefined,
      created_at: '2026-06-01T08:00:00Z',
    },
  ],
  'MRN-003': [],
  'MRN-005': [],
}

// ─────────────────────────────────────────────────────────────────────────────
// Consultations (between doctors, about a patient)
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_CONSULTATIONS: Record<string, ConsultationResponse[]> = {
  'MRN-001': [
    {
      id: 'con-001-01',
      patient_mrn: 'MRN-001',
      from_user_id: 'dr-001',
      to_user_id: 'dr-002',
      subject: '王患者骨轉移：是否需要骨科介入？',
      status: 'replied',
      created_at: '2026-05-18T09:00:00Z',
      updated_at: '2026-05-20T11:00:00Z',
      messages: [
        {
          id: 'msg-001-01-01',
          consultation_id: 'con-001-01',
          sender_id: 'dr-001',
          body: '林醫師您好，王患者目前骨轉移疼痛控制尚可，但最新 CT 顯示 T10 椎體有壓迫性骨折跡象。請問是否建議骨科會診評估脊椎穩定性，以及是否需要放射治療？謝謝。',
          created_at: '2026-05-18T09:00:00Z',
        },
        {
          id: 'msg-001-01-02',
          consultation_id: 'con-001-01',
          sender_id: 'dr-002',
          body: '陳醫師您好，已看過影像。T10 椎體雖有骨折，但目前神經學檢查穩定。建議：\n1. 安排骨科會診（重點評估是否需要椎體成形術）\n2. 疼痛科同時介入\n3. 若神經學症狀惡化，優先考慮緊急放療\n\n我明後天有門診，可以幫忙轉介骨科。',
          created_at: '2026-05-20T11:00:00Z',
        },
      ],
    },
  ],
  'MRN-002': [
    {
      id: 'con-002-01',
      patient_mrn: 'MRN-002',
      from_user_id: 'dr-001',
      to_user_id: 'dr-003',
      subject: '李患者：術後輔助放療時程與化療交替安排',
      status: 'open',
      created_at: '2026-06-02T10:00:00Z',
      updated_at: '2026-06-02T10:00:00Z',
      messages: [
        {
          id: 'msg-002-01-01',
          consultation_id: 'con-002-01',
          sender_id: 'dr-001',
          body: '黃醫師您好，李患者術後 AC-T 化療預計第 4 週期結束後（約 7 月初），希望接著進行輔助放療。請問放射科排程目前有空檔嗎？另外，化療結束到放療開始的間隔您建議幾週？感謝。',
          created_at: '2026-06-02T10:00:00Z',
        },
      ],
    },
  ],
  'MRN-003': [],
  'MRN-004': [],
  'MRN-005': [],
}

// ─────────────────────────────────────────────────────────────────────────────
// Treatment plans (fake OpenOnco engine output)
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_PLANS: Record<string, object> = {
  'plan-001': {
    plan_id: 'plan-001',
    disease_id: 'DIS-BREAST-HER2POS-MET',
    algorithm_id: 'ALG-BREAST-HER2POS-1L-MET',
    tracks: [
      {
        track_id: 'trk-001-a',
        label: 'HP + Docetaxel（標準一線）',
        label_en: 'Pertuzumab + Trastuzumab + Docetaxel',
        is_default: true,
        indication_id: 'IND-HER2-1L-HPD',
        regimen_id: 'RGM-PHESGO-DOCE',
        regimen_name: 'Pertuzumab + Trastuzumab + Docetaxel',
        evidence_level: 'I',
        nccn_category: '1',
        median_os_months: 57.1,
        selection_reason: 'HER2+ 轉移性乳癌首選：CLEOPATRA 試驗 OS 57.1 月',
      },
      {
        track_id: 'trk-001-b',
        label: 'T-DXd（HER2 ADC）',
        label_en: 'Trastuzumab deruxtecan',
        is_default: false,
        indication_id: 'IND-HER2-2L-TDXD',
        regimen_id: 'RGM-TDXD',
        regimen_name: 'Trastuzumab deruxtecan (T-DXd)',
        evidence_level: 'I',
        nccn_category: '1',
        median_os_months: 29.1,
        selection_reason: '若 HP+Taxane 治療後進展，DESTINY-Breast03 PFS 優於 T-DM1',
      },
    ],
    mdt: null,
    gaps: [
      { field: 'brain_mets', tier: 2, current_value: null, rationale: '若腦轉移陽性，需考慮 tucatinib + trastuzumab + capecitabine', recommended_test: 'MRI 腦部掃描' },
    ],
    warnings: [],
  },

  'plan-002': {
    plan_id: 'plan-002',
    disease_id: 'DIS-BREAST-ERPOS-EARLY',
    algorithm_id: 'ALG-BREAST-ERPOS-ADJ',
    tracks: [
      {
        track_id: 'trk-002-a',
        label: 'AC-T（標準輔助化療）',
        label_en: 'Doxorubicin + Cyclophosphamide → Paclitaxel',
        is_default: true,
        indication_id: 'IND-ERPOS-ADJ-ACT',
        regimen_id: 'RGM-ACT',
        regimen_name: 'AC → weekly Paclitaxel',
        evidence_level: 'I',
        nccn_category: '1',
        median_os_months: null,
        selection_reason: 'ER+/HER2- 第三期：Oncotype DX RS ≥26，AC-T 化療可降低復發',
      },
      {
        track_id: 'trk-002-b',
        label: 'Tamoxifen / AI（內分泌治療）',
        label_en: 'Aromatase inhibitor × 5-10 years',
        is_default: false,
        indication_id: 'IND-ERPOS-AI',
        regimen_id: 'RGM-AI',
        regimen_name: 'Aromatase inhibitor (Letrozole/Anastrozole/Exemestane)',
        evidence_level: 'I',
        nccn_category: '1',
        median_os_months: null,
        selection_reason: '化療後接續內分泌治療 5–10 年為標準',
      },
    ],
    mdt: null,
    gaps: [],
    warnings: [],
  },

  'plan-003': {
    plan_id: 'plan-003',
    disease_id: 'DIS-BREAST-TNBC-EARLY',
    algorithm_id: 'ALG-BREAST-TNBC-NAC',
    tracks: [
      {
        track_id: 'trk-003-a',
        label: 'Pembrolizumab + 化療（新輔助）',
        label_en: 'Pembrolizumab + Carboplatin + Paclitaxel → AC',
        is_default: true,
        indication_id: 'IND-TNBC-NAC-PEMBRO',
        regimen_id: 'RGM-PEMBRO-CARBO-PAC',
        regimen_name: 'Pembrolizumab + Carboplatin + Paclitaxel',
        evidence_level: 'I',
        nccn_category: '1',
        median_os_months: null,
        selection_reason: 'KEYNOTE-522：pCR 率 64.8% vs 51.2%（化療組），EFS 顯著改善',
      },
    ],
    mdt: null,
    gaps: [],
    warnings: ['plan_status:superseded — 術後已達 pCR，方案已完成'],
  },

  'plan-004': {
    plan_id: 'plan-004',
    disease_id: 'DIS-BREAST-BRCA1-HEREDITARY',
    algorithm_id: 'ALG-BREAST-BRCA-RISK-MGMT',
    tracks: [
      {
        track_id: 'trk-004-a',
        label: '強化監測（MRI + 乳攝）',
        label_en: 'Enhanced surveillance: annual MRI + mammography',
        is_default: true,
        indication_id: 'IND-BRCA1-SURVEILLANCE',
        regimen_id: 'RGM-SURV-MRI-MMG',
        regimen_name: '每年 MRI + 乳房攝影',
        evidence_level: 'II',
        nccn_category: '2A',
        median_os_months: null,
        selection_reason: 'BRCA1 攜帶者：強化監測可早期發現，建議 25 歲起每年 MRI',
      },
      {
        track_id: 'trk-004-b',
        label: '預防性切除術',
        label_en: 'Risk-reducing bilateral mastectomy',
        is_default: false,
        indication_id: 'IND-BRCA1-PROPHYLACTIC',
        regimen_id: 'RGM-RRSO',
        regimen_name: '風險降低性雙側乳房切除術',
        evidence_level: 'II',
        nccn_category: '2A',
        median_os_months: null,
        selection_reason: '可降低 BRCA1 乳癌風險 >95%，需與病患充分討論意願及生育規劃',
      },
    ],
    mdt: null,
    gaps: [
      { field: 'brca2', tier: 2, current_value: null, rationale: '確認是否同時有 BRCA2 突變影響後續管理', recommended_test: '胚系 BRCA 套組檢測' },
    ],
    warnings: [],
  },

  'plan-005': {
    plan_id: 'plan-005',
    disease_id: 'DIS-BREAST-ERPOS-MET',
    algorithm_id: 'ALG-BREAST-ERPOS-MET-2L',
    tracks: [
      {
        track_id: 'trk-005-a',
        label: 'Fulvestrant + Palbociclib（CDK4/6i）',
        label_en: 'Fulvestrant + Palbociclib',
        is_default: true,
        indication_id: 'IND-ERPOS-MET-CDK46',
        regimen_id: 'RGM-FULV-PALBO',
        regimen_name: 'Fulvestrant + Palbociclib',
        evidence_level: 'I',
        nccn_category: '1',
        median_os_months: 34.9,
        selection_reason: 'ESR1 突變陽性，換用 fulvestrant 繞過 ESR1 突變耐藥性，PALOMA-3 OS 34.9 月',
      },
      {
        track_id: 'trk-005-b',
        label: 'Elacestrant（口服 SERD）',
        label_en: 'Elacestrant',
        is_default: false,
        indication_id: 'IND-ERPOS-ESR1-SERD',
        regimen_id: 'RGM-ELACE',
        regimen_name: 'Elacestrant',
        evidence_level: 'I',
        nccn_category: '1',
        median_os_months: null,
        selection_reason: 'EMERALD 試驗：ESR1 突變亞族群 PFS 顯著改善（HR 0.55）',
      },
    ],
    mdt: null,
    gaps: [
      { field: 'pik3ca_mutation', tier: 2, current_value: null, rationale: 'PIK3CA 突變陽性可加用 alpelisib + fulvestrant', recommended_test: 'ctDNA PIK3CA 檢測' },
    ],
    warnings: [],
  },
}

// ─────────────────────────────────────────────────────────────────────────────
// MTD sessions
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_MTD_SESSIONS: MtdSessionResponse[] = [
  {
    id: 'mtd-session-01',
    meeting_date: '2026-06-10T08:00:00Z',
    location: '第三會議室',
    created_by: 'dr-001',
    status: 'scheduled',
    created_at: '2026-06-04T09:00:00Z',
    cases: [
      {
        id: 'mtdcase-01-01', mtd_session_id: 'mtd-session-01',
        patient_mrn: 'MRN-001', added_by: 'dr-001',
        reason: 'HER2+ 第四期骨轉移進展評估，討論是否換線',
        status: 'pending', conclusion_text: undefined,
        conclusion_by: undefined, conclusion_at: undefined,
        created_at: '2026-06-04T09:05:00Z',
      },
      {
        id: 'mtdcase-01-02', mtd_session_id: 'mtd-session-01',
        patient_mrn: 'MRN-005', added_by: 'dr-003',
        reason: 'ER+ 轉移性乳癌：ESR1 突變陽性，討論最佳二線方案',
        status: 'pending', conclusion_text: undefined,
        conclusion_by: undefined, conclusion_at: undefined,
        created_at: '2026-06-04T09:10:00Z',
      },
    ],
  },
  {
    id: 'mtd-session-00',
    meeting_date: '2026-05-28T08:00:00Z',
    location: '第三會議室',
    created_by: 'dr-001',
    status: 'closed',
    created_at: '2026-05-21T09:00:00Z',
    cases: [
      {
        id: 'mtdcase-00-01', mtd_session_id: 'mtd-session-00',
        patient_mrn: 'MRN-001', added_by: 'dr-001',
        reason: '骨轉移疼痛控制及放療評估',
        status: 'discussed',
        conclusion_text: '維持現行 HP+Docetaxel 方案，4 週後 CT 評估；疼痛科同時介入；骨科 6/5 會診。',
        conclusion_by: 'dr-001',
        conclusion_at: '2026-05-28T14:30:00Z',
        created_at: '2026-05-21T09:05:00Z',
      },
    ],
  },
]

// ─────────────────────────────────────────────────────────────────────────────
// Drug requisitions
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_DRUG_REQS = {
  'req-001': {
    id: 'req-001',
    requisition_id: 'ABCD1234',
    created_date: '2026-06-03',
    patient_mrn: 'MRN-001',
    patient_name_initials: '王●●',
    patient_birth_year: '1971',
    patient_sex: 'F',
    diagnosis_icd10: 'C50.9',
    diagnosis_text: '乳癌',
    stage: '第四期',
    treatment_intent: '姑息性治療',
    line_of_therapy: 1,
    key_biomarkers: ['HER2+', 'ER-', 'PR-'],
    indication_id: 'IND-HER2-1L-HPD',
    plan_id: 'plan-001',
    plan_track_id: 'trk-001-a',
    regimen_id: 'RGM-PHESGO-DOCE',
    regimen_name_en: 'Pertuzumab + Trastuzumab + Docetaxel',
    regimen_name_zh: '帕妥珠單抗 + 曲妥珠單抗 + 多西他賽',
    cycle_length_days: 21,
    total_cycles: '6',
    components: [],
    evidence: { nccn_category: '1', nccn_category_zh: '第一類', esmo_grade: 'A', evidence_level: 'I', evidence_level_zh: '第一級', pivotal_trial_nct: ['NCT00567190'], source_ids: [] },
    requires_prior_auth: true,
    special_approval_rationale: '依據 NCCN 第一類推薦。CLEOPATRA 試驗 OS 57.1 月。【請主治醫師確認】',
    prescribing_physician: '林志明',
    key_toxicities: ['心臟毒性監測', '輸注反應', '腹瀉', '周邊神經病變'],
  },
}

// ─────────────────────────────────────────────────────────────────────────────
// KB status (admin panel)
// ─────────────────────────────────────────────────────────────────────────────

export const MOCK_KB_STATUS = {
  ok: true,
  total_entities: 2250,
  schema_errors: 0,
  ref_errors: 0,
  last_refreshed_at: '2026-06-05T08:00:00Z',
  by_type: {
    diseases: 78,
    biomarkers: 173,
    biomarker_actionability: 438,
    regimens: 360,
    drugs: 251,
    indications: 424,
    redflags: 474,
    algorithms: 140,
    sources: 383,
  },
}
