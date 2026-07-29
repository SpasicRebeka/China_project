import type {
  ClinicalAnswerOption,
  ClinicalAnswerType,
  LocalizedClinicalText,
} from '@hering/contracts'

export type SystemId =
  | 'cardiovascular'
  | 'respiratory'
  | 'digestive'
  | 'neurologic'
  | 'endocrine'
  | 'urinary'
  | 'hematologic'

export type ComplaintId = string

export interface Point {
  x: number
  y: number
}

export interface SystemDefinition extends Point {
  id: SystemId
  label: string
  shortLabel: string
}

interface KnowledgeQuestion {
  id: string
  field: string
  prompt: LocalizedClinicalText
  answer_type: ClinicalAnswerType
  value_set?: string
  unit?: string
  source_refs: string[]
}

interface KnowledgeAssociatedSymptom {
  code: string
  label: LocalizedClinicalText
  source_refs: string[]
}

interface KnowledgeRedFlag {
  id: string
  clinician_label: LocalizedClinicalText
  source_refs: string[]
}

interface KnowledgeSymptom {
  id: string
  label: LocalizedClinicalText
  questions: KnowledgeQuestion[]
  associated_symptoms: KnowledgeAssociatedSymptom[]
  red_flags: KnowledgeRedFlag[]
}

interface FollowupTemplate {
  questions: KnowledgeQuestion[]
}

export interface KnowledgeGraphDatabase {
  kb_version: string
  response_sets?: Record<string, ClinicalAnswerOption[]>
  value_sets?: Record<string, ClinicalAnswerOption[]>
  followup_templates: Record<string, FollowupTemplate>
  symptoms: KnowledgeSymptom[]
}

interface ResolvedKnowledgeQuestion extends KnowledgeQuestion {
  options: ClinicalAnswerOption[]
}

export interface RelatedSymptom {
  id: string
  label: string
  labelText: LocalizedClinicalText
  sourceRefs: string[]
}

export interface ComplaintDefinition extends Point {
  id: ComplaintId
  label: string
  systems: SystemId[]
  related: RelatedSymptom[]
  questions: ResolvedKnowledgeQuestion[]
  associatedOptions: ClinicalAnswerOption[]
  redFlags: RelatedSymptom[]
  redFlagCount: number
  knowledgeVersion: string
}

export interface InterviewNode extends Point {
  id: string
  label: string
  question: string
  prompt: LocalizedClinicalText
  field: string
  answerType: ClinicalAnswerType
  options: ClinicalAnswerOption[]
  unit?: string
  sourceRefs: string[]
  knowledgeVersion: string
  kind: 'attribute' | 'associated'
}

export const systemDefinitions: SystemDefinition[] = [
  { id: 'cardiovascular', label: '心血管系统', shortLabel: '心血管', x: 86, y: 78 },
  { id: 'respiratory', label: '呼吸系统', shortLabel: '呼吸', x: 284, y: 58 },
  { id: 'digestive', label: '消化系统', shortLabel: '消化', x: 500, y: 98 },
  { id: 'neurologic', label: '神经系统', shortLabel: '神经', x: 94, y: 314 },
  { id: 'endocrine', label: '内分泌系统', shortLabel: '内分泌', x: 286, y: 278 },
  { id: 'urinary', label: '泌尿系统', shortLabel: '泌尿', x: 500, y: 330 },
  { id: 'hematologic', label: '血液系统', shortLabel: '血液', x: 290, y: 430 },
]

const complaintPositions: Record<string, Point> = {
  chest_pain: { x: 182, y: 142 },
  chest_tightness: { x: 306, y: 142 },
  cough: { x: 424, y: 164 },
  fever: { x: 438, y: 248 },
  abdominal_pain: { x: 422, y: 390 },
  dizziness: { x: 192, y: 300 },
  fatigue: { x: 286, y: 356 },
}

const complaintSystems: Record<string, SystemId[]> = {
  chest_pain: ['cardiovascular', 'respiratory'],
  chest_tightness: ['cardiovascular', 'respiratory'],
  cough: ['respiratory'],
  fever: ['respiratory', 'digestive', 'urinary', 'hematologic'],
  abdominal_pain: ['digestive', 'urinary'],
  dizziness: ['neurologic', 'cardiovascular', 'hematologic'],
  fatigue: ['endocrine', 'hematologic', 'neurologic'],
}

const interviewPositions: Point[] = [
  { x: 292, y: 70 },
  { x: 454, y: 116 },
  { x: 502, y: 250 },
  { x: 448, y: 378 },
  { x: 292, y: 418 },
  { x: 126, y: 378 },
  { x: 82, y: 250 },
  { x: 128, y: 116 },
]

const fieldLabels: Record<string, string> = {
  current_status: '当前状态',
  onset: '起病时间',
  episode_duration: '持续时间',
  frequency: '出现频率',
  severity_nrs: '严重程度',
  progression: '发展变化',
  functional_impact: '活动影响',
  location: '部位',
  character: '感觉性质',
  radiation: '扩散部位',
  onset_speed: '起病方式',
  triggers: '诱发因素',
  relievers: '缓解因素',
  primary_feeling: '主要感觉',
  cough_type: '咳嗽类型',
  sputum_character: '痰液特点',
  hemoptysis: '咳血',
  timing_pattern: '时间特点',
  exposures: '接触因素',
  temperature_measured: '体温测量',
  max_temperature_c: '最高体温',
  measurement_site: '测量部位',
  fever_pattern: '发热规律',
  rigors: '寒战',
  recent_travel: '旅行情况',
  sick_contact: '接触史',
  immunosuppression_context: '免疫相关',
  migration: '位置变化',
  pregnancy_possible: '妊娠可能',
  vaginal_bleeding: '异常出血',
  pattern: '发作模式',
  trigger: '诱发动作',
  experience: '感觉记录',
  walking_ability: '行走能力',
  new_hearing_change: '听力变化',
  new_tinnitus: '耳鸣变化',
  primary_experience: '主要感受',
  baseline_change: '活动变化',
  daily_pattern: '日间规律',
  rest_response: '休息反应',
  post_exertional_response: '活动后反应',
  post_exertional_recovery: '恢复时间',
  cognitive_change: '认知变化',
  upright_worse: '体位影响',
}

function fallbackPosition(index: number, total: number): Point {
  const angle = (Math.PI * 2 * index) / Math.max(total, 1) - Math.PI / 2
  return {
    x: 292 + Math.cos(angle) * 176,
    y: 244 + Math.sin(angle) * 176,
  }
}

function shortQuestionLabel(question: KnowledgeQuestion) {
  return fieldLabels[question.field] ?? question.prompt.zh.replace(/[？。]/g, '').slice(0, 6)
}

function uniqueQuestions(questions: KnowledgeQuestion[]) {
  const seen = new Set<string>()
  return questions.filter((question) => {
    if (seen.has(question.id)) return false
    seen.add(question.id)
    return true
  })
}

function resolveOptions(
  database: KnowledgeGraphDatabase,
  valueSet?: string,
): ClinicalAnswerOption[] {
  if (!valueSet) return []
  const [collection, key] = valueSet.split('.')
  if (collection === 'response_sets' && key) {
    return database.response_sets?.[key] ?? []
  }
  if (collection === 'value_sets' && key) {
    return database.value_sets?.[key] ?? []
  }
  return database.value_sets?.[valueSet]
    ?? database.response_sets?.[valueSet]
    ?? []
}

export async function loadKnowledgeGraph(apiBase = ''): Promise<KnowledgeGraphDatabase> {
  const response = await fetch(`${apiBase}/api/v1/knowledge-graph`)
  if (!response.ok) throw new Error(`Knowledge graph request failed: ${response.status}`)
  return response.json() as Promise<KnowledgeGraphDatabase>
}

export function buildComplaintDefinitions(database: KnowledgeGraphDatabase): ComplaintDefinition[] {
  const coreQuestions = database.followup_templates.core_hpi_v1?.questions ?? []
  return database.symptoms.map((symptom, index) => ({
    id: symptom.id,
    label: symptom.label.zh,
    systems: complaintSystems[symptom.id] ?? [],
    related: symptom.associated_symptoms.map((associated) => ({
      id: associated.code,
      label: associated.label.zh,
      labelText: associated.label,
      sourceRefs: associated.source_refs,
    })),
    questions: uniqueQuestions([...coreQuestions, ...symptom.questions]).map((question) => ({
      ...question,
      options: resolveOptions(database, question.value_set),
    })),
    associatedOptions: database.response_sets?.presence_v1 ?? [],
    redFlags: symptom.red_flags.map((flag) => ({
      id: flag.id,
      label: flag.clinician_label.zh,
      labelText: flag.clinician_label,
      sourceRefs: flag.source_refs,
    })),
    redFlagCount: symptom.red_flags.length,
    knowledgeVersion: database.kb_version,
    ...(complaintPositions[symptom.id] ?? fallbackPosition(index, database.symptoms.length)),
  }))
}

export function buildInterviewNodePages(complaint: ComplaintDefinition): InterviewNode[][] {
  const questionNodes = complaint.questions.map((question) => ({
    id: question.id,
    label: shortQuestionLabel(question),
    question: question.prompt.zh,
    prompt: question.prompt,
    field: question.field,
    answerType: question.answer_type,
    options: question.options,
    unit: question.unit,
    sourceRefs: question.source_refs,
    knowledgeVersion: complaint.knowledgeVersion,
    kind: 'attribute' as const,
  }))
  const associatedNodes = complaint.related.map((symptom) => ({
    id: `associated.${symptom.id}`,
    label: symptom.label,
    question: `是否同时出现${symptom.label}？`,
    prompt: {
      zh: `是否同时出现${symptom.label}？`,
      en: `Are you also experiencing ${symptom.labelText.en}?`,
    },
    field: `associated_symptoms.${symptom.id}`,
    answerType: 'single_choice' as const,
    options: complaint.associatedOptions,
    sourceRefs: symptom.sourceRefs,
    knowledgeVersion: complaint.knowledgeVersion,
    kind: 'associated' as const,
  }))
  const sourceNodes = [...questionNodes, ...associatedNodes]
  const pages: InterviewNode[][] = []

  for (let offset = 0; offset < sourceNodes.length; offset += interviewPositions.length) {
    const page = sourceNodes.slice(offset, offset + interviewPositions.length).map((node, index) => ({
      ...node,
      ...(interviewPositions[index] ?? { x: 292, y: 250 }),
    }))
    pages.push(page)
  }
  return pages
}

export function findComplaint(
  complaints: ComplaintDefinition[],
  id: ComplaintId | null,
): ComplaintDefinition | null {
  return complaints.find((complaint) => complaint.id === id) ?? null
}
