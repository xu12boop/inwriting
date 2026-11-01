// 全局类型定义：统一前后端数据契约，提升 TypeScript 规范性与可维护性

export interface RadarData {
  [key: string]: number
}

export interface LearningTask {
  task: string
  completed: boolean
}

export interface ReportData {
  id: number
  interview_id: number
  radar_data: RadarData
  learning_plan: LearningTask[]
  overall_score: number
  summary: string
}

export interface ParsedResume {
  skills?: string[]
  [key: string]: unknown
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
