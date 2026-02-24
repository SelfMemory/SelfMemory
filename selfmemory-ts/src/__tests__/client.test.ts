import { describe, it, expect, vi, beforeEach } from 'vitest'
import { SelfMemory } from '../client'
import { SelfMemoryError } from '../errors'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  }
}

function lastFetchCall() {
  const [url, options] = mockFetch.mock.calls[mockFetch.mock.calls.length - 1]
  return { url: url as string, options: options as RequestInit }
}

function lastBody() {
  const { options } = lastFetchCall()
  return JSON.parse(options.body as string)
}

beforeEach(() => {
  mockFetch.mockReset()
})

describe('SelfMemory constructor', () => {
  it('throws when apiKey is missing', () => {
    expect(() => new SelfMemory({ apiKey: '' })).toThrow('apiKey is required')
  })

  it('uses default host', () => {
    const memory = new SelfMemory({ apiKey: 'sk_test' })
    mockFetch.mockResolvedValueOnce(mockResponse({ status: 'ok' }))

    memory.health()

    const { url } = lastFetchCall()
    expect(url).toContain('https://api.selfmemory.com')
  })

  it('strips trailing slash from custom host', () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081/' })
    mockFetch.mockResolvedValueOnce(mockResponse({ status: 'ok' }))

    memory.health()

    const { url } = lastFetchCall()
    expect(url).toBe('http://localhost:8081/health')
  })
})

describe('SelfMemory auth', () => {
  it('sends Bearer token in Authorization header', () => {
    const memory = new SelfMemory({ apiKey: 'sk_im_test123' })
    mockFetch.mockResolvedValueOnce(mockResponse({ status: 'ok' }))

    memory.health()

    const { options } = lastFetchCall()
    const headers = options.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer sk_im_test123')
  })
})

describe('SelfMemory.add', () => {
  it('builds correct payload with messages and metadata', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(
      mockResponse({ success: true, memory_id: 'abc', message: 'ok' }),
    )

    await memory.add('User likes pizza', {
      tags: 'food,preferences',
      people_mentioned: 'Sarah',
      topic_category: 'personal',
      user_id: 'user_1',
    })

    const { url, options } = lastFetchCall()
    expect(url).toBe('http://localhost:8081/api/memories')
    expect(options.method).toBe('POST')

    const body = lastBody()
    expect(body.messages).toEqual([{ role: 'user', content: 'User likes pizza' }])
    expect(body.user_id).toBe('user_1')
    expect(body.metadata.tags).toBe('food,preferences')
    expect(body.metadata.people_mentioned).toBe('Sarah')
    expect(body.metadata.topic_category).toBe('personal')
  })

  it('sends empty strings for unset metadata fields', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(
      mockResponse({ success: true, memory_id: 'abc', message: 'ok' }),
    )

    await memory.add('Simple memory')

    const body = lastBody()
    expect(body.metadata.tags).toBe('')
    expect(body.metadata.people_mentioned).toBe('')
    expect(body.metadata.topic_category).toBe('')
  })
})

describe('SelfMemory.search', () => {
  it('builds correct payload with filters', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ results: [] }))

    await memory.search('meetings', {
      limit: 5,
      tags: ['work'],
      people_mentioned: ['Sarah', 'Mike'],
      threshold: 0.7,
      user_id: 'user_1',
    })

    const body = lastBody()
    expect(body.query).toBe('meetings')
    expect(body.user_id).toBe('user_1')
    expect(body.people_mentioned).toBe('Sarah,Mike')
    expect(body.filters.limit).toBe(5)
    expect(body.filters.tags).toEqual(['work'])
    expect(body.filters.threshold).toBe(0.7)
  })

  it('omits filters when no filter options provided', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ results: [] }))

    await memory.search('hello')

    const body = lastBody()
    expect(body.query).toBe('hello')
    expect(body.filters).toBeUndefined()
  })
})

describe('SelfMemory.getAll', () => {
  it('builds query params correctly', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ results: [] }))

    await memory.getAll({ limit: 50, offset: 10 })

    const { url, options } = lastFetchCall()
    expect(url).toContain('limit=50')
    expect(url).toContain('offset=10')
    expect(options.method).toBe('GET')
  })
})

describe('SelfMemory.get', () => {
  it('calls correct URL with memory ID', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ id: 'mem-123', content: 'test' }))

    await memory.get('mem-123')

    const { url } = lastFetchCall()
    expect(url).toBe('http://localhost:8081/api/memories/mem-123')
  })
})

describe('SelfMemory.delete', () => {
  it('sends DELETE request', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ message: 'deleted' }))

    await memory.delete('mem-123')

    const { url, options } = lastFetchCall()
    expect(url).toBe('http://localhost:8081/api/memories/mem-123')
    expect(options.method).toBe('DELETE')
  })
})

describe('SelfMemory.deleteAll', () => {
  it('sends DELETE to /api/memories', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ message: 'deleted', deleted_count: 5 }))

    await memory.deleteAll()

    const { url, options } = lastFetchCall()
    expect(url).toBe('http://localhost:8081/api/memories')
    expect(options.method).toBe('DELETE')
  })
})

describe('SelfMemory.searchByTags', () => {
  it('builds correct payload', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ results: [] }))

    await memory.searchByTags(['work', 'important'], { match_all: true, limit: 5 })

    const body = lastBody()
    expect(body.tags).toEqual(['work', 'important'])
    expect(body.match_all).toBe(true)
    expect(body.limit).toBe(5)
  })
})

describe('SelfMemory.temporalSearch', () => {
  it('builds correct payload', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ results: [] }))

    await memory.temporalSearch('yesterday', { semantic_query: 'meetings' })

    const body = lastBody()
    expect(body.temporal_query).toBe('yesterday')
    expect(body.semantic_query).toBe('meetings')
  })
})

describe('error handling', () => {
  it('throws SelfMemoryError on non-2xx response', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: 'Memory not found' }),
      text: () => Promise.resolve('Memory not found'),
    })

    await expect(memory.get('bad-id')).rejects.toThrow(SelfMemoryError)
    await expect(
      (async () => {
        mockFetch.mockResolvedValueOnce({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ detail: 'Memory not found' }),
          text: () => Promise.resolve('Memory not found'),
        })
        return memory.get('bad-id')
      })(),
    ).rejects.toMatchObject({ status: 404, detail: 'Memory not found' })
  })

  it('does not send Content-Type on GET requests', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ results: [] }))

    await memory.getAll()

    const { options } = lastFetchCall()
    const headers = options.headers as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
  })

  it('sends Content-Type on POST requests', async () => {
    const memory = new SelfMemory({ apiKey: 'sk_test', host: 'http://localhost:8081' })
    mockFetch.mockResolvedValueOnce(mockResponse({ results: [] }))

    await memory.search('test')

    const { options } = lastFetchCall()
    const headers = options.headers as Record<string, string>
    expect(headers['Content-Type']).toBe('application/json')
  })
})
