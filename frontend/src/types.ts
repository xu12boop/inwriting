// 全局类型定义：统一前后端数据契约，提升 TypeScript 规范性与可维护性

export interface RadarData {
  [key: string]: number
}

export interface LearningTask {
  task: string
  completed: boolean
}

export interface QuestionReview {
  question: string
  answer_digest: string
  verdict: "good" | "ok" | "weak" | string
  comment: string
}

export interface ReportData {
  id: number
  interview_id: number
  radar_data: RadarData
  learning_plan: LearningTask[]
  overall_score: number
  summary: string
  question_reviews?: QuestionReview[] | null
}

export interface ParsedResume {
  skills?: string[]
  _match?: MatchDetail
  [key: string]: unknown
}

export interface MatchedItem {
  requirement: string
  evidence: string
}

// 简历与 JD 的匹配明细：结论 + 逐条命中 + 差距项 + 检索依据
export interface MatchDetail {
  job_name?: string
  verdict?: string
  matched?: MatchedItem[]
  gaps?: string[]
  citation?: string
  jd_excerpt?: string
  retrieval_score?: number
}

export interface ResumeData {
  id: number
  match_score: number
  parsed_json: ParsedResume
}

export interface ChatMessage {
  role: "user" | "ai"
  content: string
  typing?: boolean
}
