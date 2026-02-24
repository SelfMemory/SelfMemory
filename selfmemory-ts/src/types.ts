export interface SelfMemoryConfig {
  apiKey: string
  host?: string
}

export interface MemoryMetadata {
  data?: string
  tags?: string
  people_mentioned?: string
  topic_category?: string
  created_at?: string
  updated_at?: string
  hash?: string
  user_id?: string
  createdBy?: string
  createdByEmail?: string
  [key: string]: unknown
}

export interface Memory {
  id: string
  content: string
  score?: number
  metadata?: MemoryMetadata
}

export interface AddOptions {
  tags?: string
  people_mentioned?: string
  topic_category?: string
  metadata?: Record<string, unknown>
  user_id?: string
}

export interface SearchOptions {
  limit?: number
  tags?: string[]
  people_mentioned?: string[]
  topic_category?: string
  temporal_filter?: string
  threshold?: number
  match_all_tags?: boolean
  user_id?: string
}

export interface GetAllOptions {
  limit?: number
  offset?: number
  user_id?: string
  project_id?: string
}

export interface UpdateData {
  text?: string
  metadata?: Record<string, unknown>
}

export interface DeleteAllOptions {
  user_id?: string
}

export interface AddResponse {
  success: boolean
  memory_id: string | null
  message: string
  operations?: Array<Record<string, unknown>>
}

export interface SearchResponse {
  results: Memory[]
}

export interface GetAllResponse {
  results: Memory[]
}

export interface DeleteResponse {
  message: string
}

export interface DeleteAllResponse {
  message: string
  deleted_count: number
}

export interface StatsResponse {
  total: number
  this_week: number
  tag_count: number
}

export interface HealthResponse {
  status: string
  timestamp?: string
  checks?: Record<string, unknown>
}

export interface TagSearchOptions {
  semantic_query?: string
  match_all?: boolean
  limit?: number
}

export interface PeopleSearchOptions {
  semantic_query?: string
  limit?: number
}

export interface TemporalSearchOptions {
  semantic_query?: string
  limit?: number
}
