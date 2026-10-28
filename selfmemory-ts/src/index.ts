export { SelfMemory } from './client'
export { SelfMemoryError } from './errors'
export type {
  SelfMemoryConfig,
  Memory,
  MemoryMetadata,
  AddOptions,
  AddResponse,
  SearchOptions,
  SearchResponse,
  GetAllOptions,
  GetAllResponse,
  UpdateData,
  DeleteResponse,
  DeleteAllOptions,
  DeleteAllResponse,
  StatsResponse,
  HealthResponse,
  TagSearchOptions,
  PeopleSearchOptions,
  TemporalSearchOptions,
} from './types'

// Typed /api/v1 client generated from docs/api/openapi.json (`make ts-client`)
export * as api from './generated'
