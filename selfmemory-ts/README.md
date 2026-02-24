# selfmemory

TypeScript SDK for the SelfMemory API — universal memory layer for AI apps.

## Installation

```bash
npm install selfmemory
```

## Quick Start

```typescript
import { SelfMemory } from 'selfmemory'

const memory = new SelfMemory({
  apiKey: process.env.SELFMEMORY_API_KEY!,
})

// Store a memory
await memory.add('User prefers dark mode and uses TypeScript', {
  tags: 'preferences,tech',
  topic_category: 'settings',
  user_id: 'user_123',
})

// Search memories
const results = await memory.search('what does the user prefer?', {
  user_id: 'user_123',
  limit: 5,
})

console.log(results.results)
```

## Configuration

```typescript
const memory = new SelfMemory({
  apiKey: 'sk_im_...',             // Required — project-scoped API key
  host: 'https://api.selfmemory.com', // Optional — defaults to managed API
})
```

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `apiKey` | `string` | Yes | — | Project-scoped API key from the SelfMemory dashboard |
| `host` | `string` | No | `https://api.selfmemory.com` | API base URL |

## API Reference

### `add(content, options?)`

Store a memory.

```typescript
const result = await memory.add('Meeting with Sarah about Q4 roadmap', {
  tags: 'work,meeting',
  people_mentioned: 'Sarah',
  topic_category: 'business',
  user_id: 'user_123',
})
// { success: true, memory_id: '...', message: '...' }
```

| Option | Type | Description |
|--------|------|-------------|
| `tags` | `string` | Comma-separated tags |
| `people_mentioned` | `string` | Comma-separated names |
| `topic_category` | `string` | Topic classification |
| `metadata` | `Record<string, unknown>` | Additional metadata |
| `user_id` | `string` | Scope to a specific end-user |

### `search(query, options?)`

Semantic search across memories.

```typescript
const results = await memory.search('project discussions', {
  limit: 10,
  tags: ['work', 'meeting'],
  temporal_filter: 'this_week',
  threshold: 0.7,
  user_id: 'user_123',
})
```

| Option | Type | Description |
|--------|------|-------------|
| `limit` | `number` | Max results (default: 10) |
| `tags` | `string[]` | Filter by tags |
| `people_mentioned` | `string[]` | Filter by people |
| `topic_category` | `string` | Filter by topic |
| `temporal_filter` | `string` | Time filter (`today`, `this_week`, `this_month`) |
| `threshold` | `number` | Min similarity score (0-1) |
| `match_all_tags` | `boolean` | Require all tags to match |
| `user_id` | `string` | Scope to a specific end-user |

### `getAll(options?)`

List all memories with pagination.

```typescript
const all = await memory.getAll({ limit: 50, offset: 0 })
```

### `get(memoryId)`

Get a single memory by ID.

```typescript
const mem = await memory.get('memory-uuid-here')
```

### `update(memoryId, data)`

Update a memory.

```typescript
await memory.update('memory-uuid', {
  text: 'Updated content',
  metadata: { tags: 'updated' },
})
```

### `delete(memoryId)`

Delete a single memory.

```typescript
await memory.delete('memory-uuid')
```

### `deleteAll(options?)`

Delete all memories.

```typescript
await memory.deleteAll({ user_id: 'user_123' })
```

### `searchByTags(tags, options?)`

Search by tags with optional semantic query.

```typescript
const results = await memory.searchByTags(['work', 'important'], {
  semantic_query: 'deadlines',
  match_all: true,
  limit: 10,
})
```

### `searchByPeople(people, options?)`

Search by people mentioned.

```typescript
const results = await memory.searchByPeople(['Sarah', 'Mike'], {
  semantic_query: 'project updates',
})
```

### `temporalSearch(temporalQuery, options?)`

Search by time range.

```typescript
const results = await memory.temporalSearch('yesterday', {
  semantic_query: 'meetings',
})
```

### `getStats(projectId?)`

Get memory statistics.

```typescript
const stats = await memory.getStats()
// { total: 150, this_week: 12, tag_count: 25 }
```

### `health()`

Health check.

```typescript
const status = await memory.health()
```

## Error Handling

```typescript
import { SelfMemory, SelfMemoryError } from 'selfmemory'

try {
  await memory.get('nonexistent-id')
} catch (err) {
  if (err instanceof SelfMemoryError) {
    console.error(err.status)  // 404
    console.error(err.detail)  // "Memory not found"
  }
}
```

## TypeScript

All types are exported:

```typescript
import type { Memory, SearchOptions, AddResponse } from 'selfmemory'
```

## Requirements

- Node.js 18+ (uses native `fetch`)
- Works in modern browsers

## License

MIT
