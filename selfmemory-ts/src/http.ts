import { SelfMemoryError } from './errors'

export interface RequestOptions {
  method?: string
  body?: Record<string, unknown>
  params?: Record<string, string>
}

export async function request<T>(
  baseUrl: string,
  apiKey: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = 'GET', body, params } = options

  let url = `${baseUrl}${path}`

  if (params) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value)
      }
    }
    const queryString = searchParams.toString()
    if (queryString) {
      url += `?${queryString}`
    }
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${apiKey}`,
  }

  const fetchOptions: RequestInit = { method, headers }

  if (body) {
    headers['Content-Type'] = 'application/json'
    fetchOptions.body = JSON.stringify(body)
  }

  const response = await fetch(url, fetchOptions)

  if (!response.ok) {
    let detail: string
    try {
      const errorBody = await response.json() as Record<string, unknown>
      detail = (errorBody.detail as string) || JSON.stringify(errorBody)
    } catch {
      detail = await response.text()
    }
    throw new SelfMemoryError(response.status, detail)
  }

  return response.json() as Promise<T>
}
