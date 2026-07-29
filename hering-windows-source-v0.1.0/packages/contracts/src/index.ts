export type { components, paths } from './generated/openapi'
export type { RealtimeEnvelope } from './generated/realtime'

export type Role = 'doctor' | 'patient'

export interface SessionCredentials {
  session_id: string
  expires_at: string
  doctor_token: string
  patient_token: string
}

export type SupportedPatientLocale = 'zh-CN' | 'en-US'

export type ClinicalAnswerType =
  | 'single_choice'
  | 'multi_choice'
  | 'number'
  | 'duration'
  | 'date_or_relative'
  | 'free_text'

export interface LocalizedClinicalText {
  zh: string
  en: string
}

export interface ClinicalAnswerOption {
  code: string
  label: LocalizedClinicalText
}

export interface QuestionSentPayload {
  question_id: string
  field: string
  prompt: LocalizedClinicalText
  answer_type: ClinicalAnswerType
  options: ClinicalAnswerOption[]
  unit?: string
  knowledge_version: string
  source_refs: string[]
}

export type PatientAnswerState = 'answered' | 'skipped'

export interface AnswerSubmittedPayload {
  question_id: string
  answer_type: ClinicalAnswerType
  structured_value: unknown
  display_text: string
  answer_state: PatientAnswerState
  patient_language: SupportedPatientLocale
}

export interface QuestionEventPayload {
  question_id: string
}
