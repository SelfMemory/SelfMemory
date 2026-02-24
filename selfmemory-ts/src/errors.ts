export class SelfMemoryError extends Error {
  public readonly status: number
  public readonly detail: string

  constructor(status: number, detail: string) {
    super(`SelfMemory API error (${status}): ${detail}`)
    this.name = 'SelfMemoryError'
    this.status = status
    this.detail = detail
    Object.setPrototypeOf(this, new.target.prototype)
  }
}
