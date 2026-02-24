import { request } from './http'
import type {
  SelfMemoryConfig,
  AddOptions,
  AddResponse,
  SearchOptions,
  SearchResponse,
  GetAllOptions,
  GetAllResponse,
  Memory,
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

const DEFAULT_HOST = 'https://api.selfmemory.com'

export class SelfMemory {
  private readonly apiKey: string
  private readonly host: string

  constructor(config: SelfMemoryConfig) {
    if (!config.apiKey) {
      throw new Error('apiKey is required')
    }
    this.apiKey = config.apiKey
    this.host = (config.host || DEFAULT_HOST).replace(/\/+$/, '')
  }

  async add(content: string, options: AddOptions = {}): Promise<AddResponse> {
    const { tags, people_mentioned, topic_category, metadata, user_id } = options

    const payload: Record<string, unknown> = {
      messages: [{ role: 'user', content }],
    }

    if (user_id) payload.user_id = user_id

    const metadataPayload: Record<string, unknown> = {
      tags: tags || '',
      people_mentioned: people_mentioned || '',
      topic_category: topic_category || '',
    }

    if (metadata) {
      Object.assign(metadataPayload, metadata)
    }

    payload.metadata = metadataPayload

    return request<AddResponse>(this.host, this.apiKey, '/api/memories', {
      method: 'POST',
      body: payload,
    })
  }

  async search(query: string, options: SearchOptions = {}): Promise<SearchResponse> {
    const { user_id, people_mentioned, ...filterFields } = options

    const payload: Record<string, unknown> = { query }

    if (user_id) payload.user_id = user_id
    if (people_mentioned) payload.people_mentioned = people_mentioned.join(',')

    const filters: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(filterFields)) {
      if (value !== undefined) {
        filters[key] = value
      }
    }

    if (Object.keys(filters).length > 0) {
      payload.filters = filters
    }

    return request<SearchResponse>(this.host, this.apiKey, '/api/memories/search', {
      method: 'POST',
      body: payload,
    })
  }

  async getAll(options: GetAllOptions = {}): Promise<GetAllResponse> {
    const params: Record<string, string> = {}
    if (options.limit !== undefined) params.limit = String(options.limit)
    if (options.offset !== undefined) params.offset = String(options.offset)
    if (options.user_id) params.user_id = options.user_id
    if (options.project_id) params.project_id = options.project_id

    return request<GetAllResponse>(this.host, this.apiKey, '/api/memories', { params })
  }

  async get(memoryId: string): Promise<Memory> {
    return request<Memory>(this.host, this.apiKey, `/api/memories/${memoryId}`)
  }

  async update(memoryId: string, data: UpdateData): Promise<Memory> {
    return request<Memory>(this.host, this.apiKey, `/api/memories/${memoryId}`, {
      method: 'PUT',
      body: data as Record<string, unknown>,
    })
  }

  async delete(memoryId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(this.host, this.apiKey, `/api/memories/${memoryId}`, {
      method: 'DELETE',
    })
  }

  async deleteAll(options: DeleteAllOptions = {}): Promise<DeleteAllResponse> {
    const params: Record<string, string> = {}
    if (options.user_id) params.user_id = options.user_id

    return request<DeleteAllResponse>(this.host, this.apiKey, '/api/memories', {
      method: 'DELETE',
      params,
    })
  }

  async searchByTags(tags: string[], options: TagSearchOptions = {}): Promise<SearchResponse> {
    return request<SearchResponse>(this.host, this.apiKey, '/v1/memories/tag-search/', {
      method: 'POST',
      body: {
        tags,
        semantic_query: options.semantic_query,
        match_all: options.match_all ?? false,
        limit: options.limit ?? 10,
      },
    })
  }

  async searchByPeople(
    people: string[],
    options: PeopleSearchOptions = {},
  ): Promise<SearchResponse> {
    return request<SearchResponse>(this.host, this.apiKey, '/v1/memories/people-search/', {
      method: 'POST',
      body: {
        people,
        semantic_query: options.semantic_query,
        limit: options.limit ?? 10,
      },
    })
  }

  async temporalSearch(
    temporalQuery: string,
    options: TemporalSearchOptions = {},
  ): Promise<SearchResponse> {
    return request<SearchResponse>(this.host, this.apiKey, '/v1/memories/temporal-search/', {
      method: 'POST',
      body: {
        temporal_query: temporalQuery,
        semantic_query: options.semantic_query,
        limit: options.limit ?? 10,
      },
    })
  }

  async getStats(projectId?: string): Promise<StatsResponse> {
    const params: Record<string, string> = {}
    if (projectId) params.project_id = projectId

    return request<StatsResponse>(this.host, this.apiKey, '/api/memories/stats', { params })
  }

  async health(): Promise<HealthResponse> {
    return request<HealthResponse>(this.host, this.apiKey, '/health')
  }
}
