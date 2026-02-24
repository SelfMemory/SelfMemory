import { describe, it, expect } from 'vitest'
import { SelfMemoryError } from '../errors'

describe('SelfMemoryError', () => {
  it('sets status, detail, name, and message', () => {
    const error = new SelfMemoryError(404, 'Memory not found')

    expect(error.status).toBe(404)
    expect(error.detail).toBe('Memory not found')
    expect(error.name).toBe('SelfMemoryError')
    expect(error.message).toBe('SelfMemory API error (404): Memory not found')
  })

  it('is an instance of Error and SelfMemoryError', () => {
    const error = new SelfMemoryError(500, 'Internal error')

    expect(error).toBeInstanceOf(Error)
    expect(error).toBeInstanceOf(SelfMemoryError)
  })
})
