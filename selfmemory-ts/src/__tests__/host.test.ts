import { describe, it, expect } from 'vitest'
import { stripTrailingSlashes } from '../client'

describe('stripTrailingSlashes', () => {
  it('removes every trailing slash', () => {
    expect(stripTrailingSlashes('https://api.example.com///')).toBe('https://api.example.com')
  })

  it('leaves a host without trailing slashes alone', () => {
    expect(stripTrailingSlashes('https://api.example.com')).toBe('https://api.example.com')
  })

  it('keeps slashes that are not trailing', () => {
    expect(stripTrailingSlashes('https://api.example.com/v1/')).toBe('https://api.example.com/v1')
  })

  it('handles empty and all-slash input', () => {
    expect(stripTrailingSlashes('')).toBe('')
    expect(stripTrailingSlashes('////')).toBe('')
  })

  it('stays linear on a long run of non-trailing slashes', () => {
    // The input that made /\/+$/ backtrack quadratically.
    const hostile = '/'.repeat(200_000) + 'x'
    const start = performance.now()
    expect(stripTrailingSlashes(hostile)).toBe(hostile)
    expect(performance.now() - start).toBeLessThan(100)
  })
})
